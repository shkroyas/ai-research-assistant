"""Polite page scraping for the Researcher.

For each search result URL the scraper checks robots.txt, fetches the page with
a timeout and a size limit, strips boilerplate and keeps the passage most
relevant to the query. It never raises: a page that cannot be used returns a
ScrapeResult with ok=False and a reason, and the Researcher keeps the snippet.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

USER_AGENT = "ai-research-assistant/1.0 (+https://github.com/shkroyas/ai-research-assistant)"
HTML_TYPES = ("text/html", "application/xhtml+xml")
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
    "a",
    "an",
    "analyse",
    "analyze",
    "and",
    "are",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "with",
}


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


def best_passage(paragraphs: list[str], query: str) -> str | None:
    """Pick the paragraph sharing most terms with the query; numbers add a small bonus."""
    terms = query_terms(query)
    if not paragraphs:
        return None

    def score(text: str) -> float:
        words = set(re.findall(r"[a-z0-9]+", text.lower()))
        has_number = bool(re.search(r"\d", text))
        return len(terms & words) + (0.5 if has_number else 0.0)

    best = max(paragraphs, key=score)
    if terms and score(best) < 1:
        return None
    return _trim(best)


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
    ) -> None:
        self._client = client or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        )
        self._client.headers["User-Agent"] = USER_AGENT
        self.max_bytes = max_bytes
        self.max_workers = max_workers
        self._robots: dict[str, RobotFileParser | None] = {}

    def scrape_many(self, urls: list[str], query: str) -> dict[str, ScrapeResult]:
        unique = list(dict.fromkeys(u for u in urls if u))
        if not unique:
            return {}
        # robots.txt is read once per site, before the parallel fetches.
        for url in unique:
            self._robots_for(url)
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            results = pool.map(lambda u: self.scrape(u, query), unique)
        return {r.url: r for r in results}

    def scrape(self, url: str, query: str) -> ScrapeResult:
        try:
            if urlsplit(url).scheme not in ("http", "https"):
                return ScrapeResult(url=url, ok=False, reason="not an http(s) URL")
            if not self._allowed(url):
                return ScrapeResult(url=url, ok=False, reason="disallowed by robots.txt")
            html = self._fetch_html(url)
            passage = best_passage(extract_paragraphs(html), query)
            if passage is None:
                return ScrapeResult(url=url, ok=False, reason="no relevant passage on page")
            return ScrapeResult(url=url, ok=True, passage=passage)
        except _Skip as exc:
            return ScrapeResult(url=url, ok=False, reason=str(exc))
        except httpx.TimeoutException:
            return ScrapeResult(url=url, ok=False, reason="timed out")
        except httpx.HTTPError as exc:
            return ScrapeResult(url=url, ok=False, reason=f"request failed: {type(exc).__name__}")

    def _fetch_html(self, url: str) -> str:
        with self._client.stream("GET", url) as response:
            if response.status_code >= 400:
                raise _Skip(f"HTTP {response.status_code}")
            content_type = response.headers.get("content-type", "").split(";")[0].strip()
            if content_type not in HTML_TYPES:
                raise _Skip(f"not HTML ({content_type or 'unknown type'})")
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > self.max_bytes:
                    raise _Skip("page larger than the size limit")
            return body.decode(response.encoding or "utf-8", errors="replace")

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
            except httpx.HTTPError:
                parser = None
            self._robots[site] = parser
        return self._robots[site]

    def _allowed(self, url: str) -> bool:
        parser = self._robots_for(url)
        return parser is None or parser.can_fetch(USER_AGENT, url)


class _Skip(Exception):
    """A page that was fetched but cannot be used."""
