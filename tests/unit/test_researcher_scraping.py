"""The Researcher uses scraped passages and falls back to search snippets."""

from market_research.agents import Researcher
from market_research.llm import FakeLLM
from market_research.models import Finding, ResearchState, domain_of
from market_research.scraper import ScrapeResult
from market_research.search import SampleDataSearch, SearchResult
from tests.conftest import FakeSearch


class FakeScraper:
    def __init__(self, pages: dict[str, ScrapeResult]) -> None:
        self.pages = pages
        self.calls: list[tuple[list[str], str, list[str]]] = []

    def scrape_many(self, urls: list[str], query: str, focus=()) -> dict[str, ScrapeResult]:
        self.calls.append((urls, query, list(focus)))
        return {u: self.pages[u] for u in urls if u in self.pages}


RESULTS = [
    SearchResult(title="A", url="https://www.a.example/1", content="Snippet A"),
    SearchResult(title="B", url="https://b.example/2", content="Snippet B"),
    SearchResult(title="C", url=None, content="Snippet C"),
]


def run(researcher: Researcher, query: str = "Nepal food delivery") -> ResearchState:
    return researcher.run(ResearchState(query=query))


def test_scraped_passage_replaces_snippet_and_failures_keep_snippet() -> None:
    scraper = FakeScraper(
        {
            "https://www.a.example/1": ScrapeResult(
                url="https://www.a.example/1", ok=True, passage="Full passage A"
            ),
            "https://b.example/2": ScrapeResult(
                url="https://b.example/2", ok=False, reason="timed out"
            ),
        }
    )
    llm = FakeLLM([{"queries": ["q"]}])
    state = run(Researcher(llm, FakeSearch(RESULTS), scraper=scraper))

    a, b, c = state.findings
    assert (a.claim, a.evidence, a.domain) == ("Full passage A", "scraped page", "a.example")
    assert (b.claim, b.evidence) == ("Snippet B", "search snippet")
    assert (c.claim, c.evidence, c.domain) == ("Snippet C", "search snippet", None)

    # URL-less results are not sent to the scraper; the query is.
    assert scraper.calls == [
        (["https://www.a.example/1", "https://b.example/2"], "Nepal food delivery", ["Nepal"])
    ]

    pages_step = next(t for t in state.trace if t.action == "read source pages")
    assert pages_step.detail == {"used": 1, "skipped": {"https://b.example/2": "timed out"}}
    assert state.trace[-1].detail["scraped"] == 1


def test_sample_data_is_never_scraped() -> None:
    scraper = FakeScraper({})
    llm = FakeLLM([{"queries": ["food delivery Nepal"]}])
    state = run(Researcher(llm, SampleDataSearch(), scraper=scraper), "food delivery in Nepal")
    assert state.findings and all(f.evidence == "sample data" for f in state.findings)
    assert scraper.calls == []


def test_without_scraper_findings_use_snippets() -> None:
    llm = FakeLLM([{"queries": ["q"]}])
    state = run(Researcher(llm, FakeSearch(RESULTS)))
    assert [f.evidence for f in state.findings] == ["search snippet"] * 3
    assert all(t.action != "read source pages" for t in state.trace)


def test_domain_is_exported_with_the_finding() -> None:
    finding = Finding(id="F1", claim="x", source_title="t", source_url="https://www.x.example/a")
    assert finding.model_dump()["domain"] == "x.example"
    assert domain_of(None) is None


def test_pipeline_attaches_scraper_only_when_enabled() -> None:
    from market_research import pipeline
    from market_research.config import Settings
    from market_research.scraper import PageScraper

    base = Settings(_env_file=None, llm_providers="groq", groq_api_keys="k1")
    on = pipeline.build_orchestrator(base, "groq")
    off = pipeline.build_orchestrator(base.model_copy(update={"scrape_pages": False}), "groq")
    assert isinstance(on.researcher.scraper, PageScraper)
    assert off.researcher.scraper is None


def test_researcher_ranks_focus_first_and_drops_masked_results() -> None:
    results = [
        SearchResult(
            title="Global report", url="https://g.example/1", content="Global market grows 9%."
        ),
        SearchResult(
            title="Statista", url="https://s.example/1", content="Revenue is US$ **** in ****."
        ),
        SearchResult(
            title="Kathmandu Post", url="https://k.example/1", content="Foodmandu leads Nepal."
        ),
    ]
    llm = FakeLLM([{"focus": ["Nepal"], "queries": ["food delivery market size"]}])
    search = FakeSearch(results)
    state = run(Researcher(llm, search), "Analyze the food delivery market in Nepal")

    assert search.queries == ["food delivery market size Nepal"]
    assert [(f.source_title, f.on_focus) for f in state.findings] == [
        ("Kathmandu Post", True),
        ("Global report", False),
    ]
    collected = state.trace[-1].detail
    assert (collected["on_focus"], collected["dropped_unusable"]) == (1, 1)
