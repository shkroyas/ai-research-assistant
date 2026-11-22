"""Polite page scraping for the Researcher.

For each search result URL the scraper checks robots.txt, fetches the page with
a timeout and a size limit, strips boilerplate and keeps the passage most
relevant to the query. It never raises: a page that cannot be used returns a
ScrapeResult with ok=False and a reason, and the Researcher keeps the snippet.
"""

import io
import ipaddress
import logging
import re
import socket
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from market_research.evidence import MASKED, clean_evidence

USER_AGENT = "ai-research-assistant/1.0 (+https://github.com/shkroyas/ai-research-assistant)"
HTML_TYPES = ("text/html", "application/xhtml+xml")
PDF_TYPE = "application/pdf"
# A footnote number glued to a unit in PDF text, e.g. "billion2" or "%3".
FOOTNOTE_MARK = re.compile(r"\b(thousand|million|billion|trillion|percent)\d{1,2}\b|(%)\d{1,2}\b")
BOILERPLATE_TAGS = (
    "script",
    "style",
    "noscript",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "svg",
    "iframe",
    "button",
)
MIN_PARAGRAPH_CHARS = 60
MAX_PASSAGE_CHARS = 600
STOP_WORDS = {
    "a", "about", "an", "analyse", "analyze", "and", "are", "compare", "comparison",
    "does", "for", "from", "give", "how", "in", "is", "me", "of", "on", "or",
    "overview", "research", "tell", "the", "to", "versus", "vs", "what", "which",
    "who", "why", "with",
}  # fmt: skip


def is_public_host(host: str, resolve: Callable[..., list] = socket.getaddrinfo) -> bool:
    """False when a host is, or resolves to, a private, loopback or link-local address.

    Search results are untrusted, so a result (or a redirect) pointing at
    localhost or a cloud metadata address such as 169.254.169.254 is never fetched.
    A name that does not resolve is left to the HTTP client, which will fail on it.
    """
    host = host.strip("[]").lower()
    if not host or host == "localhost" or host.endswith((".localhost", ".internal", ".local")):
        return False
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = resolve(host, None)
        except (OSError, UnicodeError):
            return True
        addresses = [ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos]
    return all(address.is_global for address in addresses)


def pdf_paragraphs(data: bytes, max_pages: int) -> list[str]:
    """Readable paragraphs from the first pages of a PDF report.

    PDF text has no reliable paragraph marks, so lines are joined and the text is
    cut into sentence groups of a few hundred characters for passage scoring.
    """
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise _Skip("PDF is encrypted")
        pages = [page.extract_text() or "" for page in reader.pages[:max_pages]]
    except _Skip:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        logging.getLogger(__name__).info("Could not read PDF: %s", exc)
        raise _Skip("PDF could not be read") from exc
    paragraphs: list[str] = []
    for page in pages:
        text = " ".join(page.replace("-\n", "").split())
        text = FOOTNOTE_MARK.sub(
            lambda m: m.group(1) or m.group(2), text
        )  # "billion2" -> "billion"
        chunk = ""
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            chunk = f"{chunk} {sentence}".strip()
            if len(chunk) >= MAX_PASSAGE_CHARS // 2:
                paragraphs.append(chunk)
                chunk = ""
        if len(chunk) >= MIN_PARAGRAPH_CHARS:
            paragraphs.append(chunk)
    return paragraphs


class ScrapeResult(BaseModel):
    url: str
    ok: bool
    passage: str | None = None
    reason: str | None = None


def query_terms(query: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", query.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) > 1}


def extract_paragraphs(html: str) -> list[str]:
    """Return readable paragraphs from a page, without navigation and scripts."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(BOILERPLATE_TAGS):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    blocks = root.find_all(["p", "li", "h2", "h3", "td"]) or [root]
    paragraphs = []
    for block in blocks:
        text = " ".join(block.get_text(" ", strip=True).split())
        if len(text) >= MIN_PARAGRAPH_CHARS:
            paragraphs.append(text)
    return paragraphs


def best_passage(
    paragraphs: list[str], query: str, focus: list[str] | tuple[str, ...] = ()
) -> str | None:
    """Pick the paragraph sharing most terms with the query.

    Paragraphs naming the focus (e.g. 'Nepal') score extra, numbers add a small bonus,
    and paragraphs with masked figures ('US$ ****') are never chosen.
    """
    terms = query_terms(query)
    focus_terms = {t for f in focus for t in query_terms(f)}
    paragraphs = [p for p in paragraphs if not MASKED.search(p)]
    if not paragraphs:
        return None

    def score(text: str) -> float:
        words = set(re.findall(r"[a-z0-9]+", text.lower()))
        has_number = bool(re.search(r"\d", text))
        return len(terms & words) + 2 * len(focus_terms & words) + (0.5 if has_number else 0.0)

    best = max(paragraphs, key=score)
    if terms and score(best) < 1:
        return None
    return _trim(clean_evidence(best)) or None


def _trim(text: str) -> str:
    if len(text) <= MAX_PASSAGE_CHARS:
        return text
    cut = text[: MAX_PASSAGE_CHARS - 3]
    return cut[: cut.rfind(" ")].rstrip(",;:") + "..."


class PageScraper:
    """Fetch and condense result pages, respecting robots.txt."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        timeout: float = 8.0,
        max_bytes: int = 2_000_000,
        max_workers: int = 4,
        resolve: Callable[..., list] = socket.getaddrinfo,
        read_pdfs: bool = False,
        max_pdf_bytes: int = 10_000_000,
        max_pdf_pages: int = 20,
    ) -> None:
        self._client = client or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        )
        self._client.headers["User-Agent"] = USER_AGENT
        self._resolve = resolve
        # Checked on every request, so a redirect cannot lead to a private address either.
        self._client.event_hooks["request"] = [
            *self._client.event_hooks.get("request", []),
            self._check_public,
        ]
        self.max_bytes = max_bytes
        self.max_workers = max_workers
        self.read_pdfs = read_pdfs
        self.max_pdf_bytes = max_pdf_bytes
        self.max_pdf_pages = max_pdf_pages
        self._robots: dict[str, RobotFileParser | None] = {}

    def scrape_many(
        self, urls: list[str], query: str, focus: list[str] | tuple[str, ...] = ()
    ) -> dict[str, ScrapeResult]:
        unique = list(dict.fromkeys(u for u in urls if u))
        if not unique:
            return {}
        # robots.txt is read once per site, before the parallel fetches.
        for url in unique:
            self._robots_for(url)
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            results = pool.map(lambda u: self.scrape(u, query, focus), unique)
        return {r.url: r for r in results}

    def scrape(self, url: str, query: str, focus: list[str] | tuple[str, ...] = ()) -> ScrapeResult:
        try:
            if urlsplit(url).scheme not in ("http", "https"):
                return ScrapeResult(url=url, ok=False, reason="not an http(s) URL")
            if not self._allowed(url):
                return ScrapeResult(url=url, ok=False, reason="disallowed by robots.txt")
            paragraphs = self._fetch_paragraphs(url)
            passage = best_passage(paragraphs, query, focus)
            if passage is None:
                return ScrapeResult(url=url, ok=False, reason="no relevant passage on page")
            return ScrapeResult(url=url, ok=True, passage=passage)
        except _Skip as exc:
            return ScrapeResult(url=url, ok=False, reason=str(exc))
        except httpx.TimeoutException:
            return ScrapeResult(url=url, ok=False, reason="timed out")
        except httpx.HTTPError as exc:
            return ScrapeResult(url=url, ok=False, reason=f"request failed: {type(exc).__name__}")

    def _check_public(self, request: httpx.Request) -> None:
        if not is_public_host(request.url.host, self._resolve):
            raise _Skip("not a public address")

    def _fetch_paragraphs(self, url: str) -> list[str]:
        """Download a web page (or, when enabled, a PDF report) and return its paragraphs."""
        with self._client.stream("GET", url) as response:
            if response.status_code >= 400:
                raise _Skip(f"HTTP {response.status_code}")
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type == PDF_TYPE and not self.read_pdfs:
                raise _Skip("PDF report (PDF reading is off)")
            if content_type not in (*HTML_TYPES, PDF_TYPE):
                raise _Skip(f"not HTML ({content_type or 'unknown type'})")
            is_pdf = content_type == PDF_TYPE
            limit = self.max_pdf_bytes if is_pdf else self.max_bytes
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > limit:
                    raise _Skip(f"{'PDF' if is_pdf else 'page'} larger than the size limit")
            if is_pdf:
                return pdf_paragraphs(bytes(body), self.max_pdf_pages)
            return extract_paragraphs(body.decode(response.encoding or "utf-8", errors="replace"))

    def _robots_for(self, url: str) -> RobotFileParser | None:
        parts = urlsplit(url)
        site = f"{parts.scheme}://{parts.netloc}"
        if site not in self._robots:
            parser: RobotFileParser | None = RobotFileParser()
            try:
                response = self._client.get(f"{site}/robots.txt")
                if response.status_code in (401, 403):
                    parser.disallow_all = True  # type: ignore[union-attr]
                elif response.status_code >= 400:
                    parser = None  # no robots.txt: everything is allowed
                else:
                    parser.parse(response.text.splitlines())  # type: ignore[union-attr]
            except (httpx.HTTPError, _Skip):
                parser = None
            self._robots[site] = parser
        return self._robots[site]

    def _allowed(self, url: str) -> bool:
        parser = self._robots_for(url)
        return parser is None or parser.can_fetch(USER_AGENT, url)


class _Skip(Exception):
    """A page that was fetched but cannot be used."""
