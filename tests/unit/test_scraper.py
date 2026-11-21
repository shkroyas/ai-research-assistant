"""Page scraping, fully offline through httpx.MockTransport."""

import httpx
import pytest

from market_research.scraper import (
    USER_AGENT,
    PageScraper,
    best_passage,
    extract_paragraphs,
    query_terms,
)

QUERY = "Analyze the food delivery market in Nepal"

ARTICLE = """
<html><head><title>Delivery</title><script>var tracking = 1;</script></head>
<body>
  <nav><p>Home | News | Business | Technology | Sport | Contact us today please</p></nav>
  <article>
    <h1>Food delivery in Nepal</h1>
    <p>Short.</p>
    <p>Cookie consent: we use cookies to personalise content and analyse our traffic here.</p>
    <p>Food delivery in Nepal grew 40% in 2025, led by Foodmandu and Pathao Food in Kathmandu.</p>
  </article>
  <footer><p>Copyright 2026 Example Media. All rights reserved. Terms and privacy.</p></footer>
</body></html>
"""


def make_scraper(handler, **kwargs) -> PageScraper:
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    return PageScraper(client=client, **kwargs)


def html_response(body: str = ARTICLE, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=body, headers={"content-type": "text/html; charset=utf-8"})


def site(pages: dict[str, httpx.Response], robots: str | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots) if robots else httpx.Response(404)
        return pages.get(str(request.url), httpx.Response(404))

    return handler


def test_query_terms_drop_stop_words() -> None:
    assert query_terms(QUERY) == {"food", "delivery", "market", "nepal"}


def test_extract_paragraphs_strips_boilerplate_and_prefers_article() -> None:
    paragraphs = extract_paragraphs(ARTICLE)
    assert any("grew 40%" in p for p in paragraphs)
    assert not any("Copyright" in p or "Home | News" in p for p in paragraphs)
    assert "Short." not in paragraphs
    assert not any("tracking" in p for p in paragraphs)


def test_best_passage_picks_most_relevant_paragraph() -> None:
    passage = best_passage(extract_paragraphs(ARTICLE), QUERY)
    assert passage is not None and passage.startswith("Food delivery in Nepal grew 40%")


def test_best_passage_trims_long_text_on_a_word_boundary() -> None:
    long = "Nepal food delivery " + "word " * 300
    passage = best_passage([long], QUERY)
    assert passage is not None and len(passage) <= 600 and passage.endswith("...")


def test_best_passage_returns_none_when_nothing_relevant() -> None:
    assert (
        best_passage(["Completely unrelated text about the weather in Oslo today."], QUERY) is None
    )
    assert best_passage([], QUERY) is None


def test_scrape_returns_relevant_passage_and_sends_user_agent() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("user-agent", ""))
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return html_response()

    scraper = make_scraper(handler)
    result = scraper.scrape("https://news.example/nepal", QUERY)
    assert result.ok and result.passage and "Foodmandu" in result.passage
    assert all(ua == USER_AGENT for ua in seen)


def test_robots_txt_disallow_is_respected() -> None:
    handler = site(
        {"https://blocked.example/private/page": html_response()},
        robots="User-agent: *\nDisallow: /private/",
    )
    result = make_scraper(handler).scrape("https://blocked.example/private/page", QUERY)
    assert not result.ok and result.reason == "disallowed by robots.txt"


def test_robots_txt_forbidden_means_disallow_all() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(403)
        return html_response()

    result = make_scraper(handler).scrape("https://locked.example/page", QUERY)
    assert not result.ok and result.reason == "disallowed by robots.txt"


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (
            httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"}),
            "not HTML (application/pdf)",
        ),
        (html_response(status=503), "HTTP 503"),
        (
            html_response("<html><body><p>Nothing useful here at all, sorry.</p></body></html>"),
            "no relevant passage on page",
        ),
    ],
)
def test_unusable_pages_report_a_reason(response: httpx.Response, reason: str) -> None:
    handler = site({"https://x.example/a": response})
    result = make_scraper(handler).scrape("https://x.example/a", QUERY)
    assert not result.ok and result.reason == reason


def test_size_limit_stops_reading() -> None:
    big = html_response("<p>Nepal food delivery " + "x" * 5000 + "</p>")
    handler = site({"https://big.example/a": big})
    result = make_scraper(handler, max_bytes=1000).scrape("https://big.example/a", QUERY)
    assert not result.ok and result.reason == "page larger than the size limit"


def test_timeout_and_network_errors_never_raise() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        raise httpx.ReadTimeout("slow", request=request)

    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    assert make_scraper(timeout).scrape("https://slow.example/a", QUERY).reason == "timed out"
    result = make_scraper(refused).scrape("https://down.example/a", QUERY)
    assert not result.ok and result.reason == "request failed: ConnectError"


def test_non_http_urls_are_skipped() -> None:
    result = make_scraper(site({})).scrape("ftp://files.example/a", QUERY)
    assert result.reason == "not an http(s) URL"


def test_scrape_many_deduplicates_and_reads_robots_once_per_site() -> None:
    robots_reads: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            robots_reads.append(request.url.host)
            return httpx.Response(404)
        return html_response()

    urls = [
        "https://a.example/1",
        "https://a.example/2",
        "https://a.example/1",
        "",
        "https://b.example/1",
    ]
    results = make_scraper(handler).scrape_many(urls, QUERY)
    assert sorted(results) == ["https://a.example/1", "https://a.example/2", "https://b.example/1"]
    assert all(r.ok for r in results.values())
    assert sorted(robots_reads) == ["a.example", "b.example"]
