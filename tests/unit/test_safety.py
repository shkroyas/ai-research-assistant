"""Failure paths: nothing the outside world sends should crash a run (spec 007)."""

import httpx
import pytest

from market_research.agents import Researcher
from market_research.llm import FakeLLM
from market_research.models import ResearchState
from market_research.prompts import ANALYST_SYSTEM, CRITIC_SYSTEM
from market_research.scraper import PageScraper, is_public_host
from market_research.search import SearchResult

ARTICLE = (
    "<html><body><p>Food delivery in Nepal grew 40% in 2025, led by Foodmandu.</p></body></html>"
)


def resolver(address: str):
    return lambda host, port: [(2, 1, 6, "", (address, 0))]


@pytest.mark.parametrize(
    "host",
    ["localhost", "127.0.0.1", "169.254.169.254", "10.0.0.5", "[::1]", "printer.local"],
)
def test_private_and_metadata_addresses_are_not_public(host: str) -> None:
    assert not is_public_host(host, resolver("8.8.8.8"))


def test_names_resolving_to_private_addresses_are_not_public() -> None:
    assert not is_public_host("evil.example", resolver("192.168.1.1"))
    assert is_public_host("news.example", resolver("93.184.216.34"))


def test_redirect_to_metadata_address_is_never_followed() -> None:
    fetched: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.host == "news.example":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest"})
        return httpx.Response(200, text=ARTICLE, headers={"content-type": "text/html"})

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    scraper = PageScraper(client=client, resolve=resolver("93.184.216.34"))
    result = scraper.scrape("https://news.example/a", "food delivery Nepal")
    assert not result.ok and result.reason == "not a public address"
    assert not any("169.254" in url for url in fetched)


class FlakySearch:
    name = "flaky"

    def __init__(self) -> None:
        self.calls = 0

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError("network down")
        return [SearchResult(title="K", url="https://k.example/1", content="Foodmandu in Nepal.")]


def test_a_failed_search_is_skipped_not_fatal() -> None:
    llm = FakeLLM([{"focus": ["Nepal"], "queries": ["a Nepal", "b Nepal"]}])
    state = Researcher(llm, FlakySearch()).run(ResearchState(query="food delivery in Nepal"))
    assert len(state.findings) == 1
    failed = next(t for t in state.trace if t.action == "searches failed")
    assert failed.detail == {"failed": {"a Nepal": "ConnectionError"}}


def test_prompts_tell_models_to_ignore_instructions_in_sources() -> None:
    assert "ignore" in ANALYST_SYSTEM and "instructions" in ANALYST_SYSTEM
    assert "not instructions" in CRITIC_SYSTEM
