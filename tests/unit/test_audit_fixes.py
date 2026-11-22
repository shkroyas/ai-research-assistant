"""Fixes from the full test and audit of the project (spec 011)."""

import logging
from datetime import UTC, datetime

import httpx
import pytest

from market_research.agents import Analyst, Critic, Orchestrator, Researcher
from market_research.agents.researcher import url_key
from market_research.config import Settings, configure_logging
from market_research.evidence import clean_evidence, has_masked, rank_results
from market_research.grounding import check_grounding
from market_research.llm import FakeLLM
from market_research.models import Brief, Competitor, Finding, QualityReport, ResearchState
from market_research.prompts import ANALYST_SYSTEM, RESEARCHER_SYSTEM
from market_research.render import brief_to_markdown, note_with_refs
from market_research.scraper import (
    PageScraper,
    ScrapeResult,
    extract_paragraphs,
    pdf_text_chunks,
)
from market_research.search import SampleDataSearch, SearchResult
from tests.conftest import FakeSearch
from ui.text import grounding_status

# --- R1: .env.example is safe to copy as it is -----------------------------------


def test_env_example_copied_as_is_keeps_offline_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("TAVILY_API_KEY", "GROQ_API_KEYS"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=".env.example")
    assert settings.web_search_enabled is False
    assert settings.groq_key_list == []


def test_blank_keys_count_as_unset() -> None:
    settings = Settings(_env_file=None, tavily_api_key="   ", groq_api_keys=" ")
    assert settings.tavily_api_key is None
    assert settings.web_search_enabled is False
    assert settings.groq_key_list == []


# --- R2: markdown bold is not a masked figure -------------------------------------


def test_bold_text_is_kept_in_evidence() -> None:
    assert clean_evidence("**Foodmandu** leads Nepal food delivery in Kathmandu.") == (
        "Foodmandu leads Nepal food delivery in Kathmandu."
    )


def test_masked_figures_are_still_dropped() -> None:
    assert clean_evidence("Revenue was US$ ****** million in ****.") == ""
    assert has_masked("Revenue was US$ **5** million in ****.")
    assert has_masked("Share was ██ percent.")
    assert not has_masked("**Foodmandu** and **Pathao Food** lead.")


def test_bold_in_the_brief_passes_grounding() -> None:
    findings = [Finding(id="F1", claim="Foodmandu leads Nepal.", source_title="A")]
    brief = Brief(
        summary="**Foodmandu** leads [F1].",
        observations=["**Foodmandu** leads Nepal [F1]"],
        competitors=[Competitor(name="Foodmandu", note="**Leader**", finding_ids=["F1"])],
    )
    assert check_grounding(brief, findings, "market", ["Nepal"]) == []


# --- R3: LOG_LEVEL is applied ------------------------------------------------------


def test_log_level_sets_the_package_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = logging.getLogger("market_research")
    monkeypatch.setattr(logger, "level", logger.level)  # restored after the test
    root_handlers = list(logging.getLogger().handlers)
    configure_logging("debug")
    configure_logging("DEBUG")
    assert logger.level == logging.DEBUG
    assert len(logging.getLogger().handlers) <= max(len(root_handlers), 1)
    configure_logging("not-a-level")
    assert logger.level == logging.INFO


# --- R4: the search plan knows today's date ----------------------------------------


def test_planning_prompt_gives_todays_date() -> None:
    llm = FakeLLM([{"kind": "market", "focus": ["Nepal"], "queries": ["Nepal food delivery"]}])
    Researcher(llm, FakeSearch([])).plan("Food delivery in Nepal")
    assert f"Today's date: {datetime.now(UTC):%Y-%m-%d}" in llm.calls[0]["prompt"]
    assert "most recent" in RESEARCHER_SYSTEM


# --- R5: the same article is one finding --------------------------------------------


@pytest.mark.parametrize(
    "variant",
    [
        "https://finance.yahoo.com/news/tesla-record.html?fr=sycsrp_catchall",
        "https://finance.yahoo.com/news/tesla-record.html?utm_source=x&utm_medium=y",
        "https://finance.yahoo.com/news/tesla-record.html?fbclid=abc&gclid=def&ref=home",
    ],
)
def test_tracking_parameters_do_not_make_a_new_page(variant: str) -> None:
    assert url_key(variant) == url_key("https://finance.yahoo.com/news/tesla-record.html")


def test_real_query_parameters_are_kept_in_any_order() -> None:
    assert url_key("https://a.com/x?id=5&page=2") == url_key("https://a.com/x?page=2&id=5")
    assert url_key("https://a.com/x?id=5") != url_key("https://a.com/x?id=6")


class PassageScraper:
    def __init__(self, passages: dict[str, str]) -> None:
        self.passages = passages

    def scrape_many(self, urls, query, focus=()):
        return {u: ScrapeResult(url=u, ok=True, passage=self.passages[u]) for u in urls}


def test_mirrored_articles_become_one_finding() -> None:
    text = "Tesla delivered 1.8 million vehicles in 2025, its revenue was $94.8 billion."
    results = [
        SearchResult(title="Investing AU", url="https://au.investing.com/t", content="Tesla a"),
        SearchResult(title="Investing", url="https://investing.com/t", content="Tesla b"),
        SearchResult(title="Reuters", url="https://reuters.com/t", content="Tesla c"),
    ]
    scraper = PassageScraper(
        {
            "https://au.investing.com/t": text,
            "https://investing.com/t": text,
            "https://reuters.com/t": "Tesla faces price cuts from BYD in China.",
        }
    )
    plan = {"kind": "company", "focus": ["Tesla"], "queries": ["Tesla revenue"]}
    state = Researcher(FakeLLM([plan]), FakeSearch(results), scraper=scraper).run(
        ResearchState(query="Research Tesla")
    )
    assert [(f.id, f.source_title) for f in state.findings] == [
        ("F1", "Investing AU"),
        ("F2", "Reuters"),
    ]
    assert state.trace[-1].detail["duplicates"] == 1


# --- R6: no findings is said plainly ------------------------------------------------


def test_no_findings_is_a_warning_not_a_success() -> None:
    def report(findings: int, problems: list[str] | None = None) -> QualityReport:
        return QualityReport(
            findings=findings, cited=0, citation_coverage=0, grounding_problems=problems or []
        )

    assert grounding_status(report(0))[0] == "warning"
    assert grounding_status(report(3))[0] == "success"
    assert grounding_status(report(3, ["x"]))[0] == "error"


def test_analyst_is_told_not_to_name_companies_outside_the_findings() -> None:
    assert "missing_information" in ANALYST_SYSTEM
    assert "that no finding names" in ANALYST_SYSTEM


def test_offline_mode_says_which_sample_topics_exist() -> None:
    plan = {"kind": "company", "focus": ["Tesla"], "queries": ["Tesla revenue"]}
    state = Researcher(FakeLLM([plan]), SampleDataSearch()).run(
        ResearchState(query="Research Tesla")
    )
    assert state.findings == []
    assert "food delivery market in Nepal" in (state.notice or "")
    state.draft = Brief(summary="Nothing was found.")
    assert "food delivery market in Nepal" in brief_to_markdown(state)


# --- R7: link lists and abbreviation pages are not passages ------------------------


def test_link_lists_are_skipped() -> None:
    page = (
        "<article><p>Also, read: <a href='/1'>Khalti is now a Payment Service Provider in "
        "Nepal</a> <a href='/2'>Nepal's Card Payment Switch is coming soon</a></p>"
        "<p>eSewa had more than 4 million users in Nepal by 2025, ahead of Khalti, "
        "according to <a href='/nrb'>NRB</a> data.</p></article>"
    )
    assert extract_paragraphs(page) == [
        "eSewa had more than 4 million users in Nepal by 2025, ahead of Khalti, "
        "according to NRB data."
    ]


def test_pdf_text_without_full_stops_is_cut_and_abbreviation_lists_are_skipped() -> None:
    acronyms = (
        "Digital Financial Services in Nepal Abbreviations and acronyms ADB Asian Development "
        "Bank AML Anti-Money Laundering API Application Programming Interface ATM Automated "
        "Teller Machine BFI Bank and Financial Institution CBS Core Banking System "
    ) * 3
    assert pdf_text_chunks(acronyms) == []
    prose = "Digital payments in Nepal grew fast and wallets reached millions of users " * 12
    chunks = pdf_text_chunks(prose)
    assert len(chunks) > 1
    assert all(len(c) <= 600 for c in chunks)
    # A short sentence followed by a long one is never merged past the limit.
    mixed = pdf_text_chunks("Wallets grew in Nepal. " * 12 + "Banks in Nepal " * 30 + "led.")
    assert all(len(c) <= 600 for c in mixed)


# --- R8: the scraper's HTTP client is closed and asks for PDFs ------------------------


def test_scraper_closes_its_own_client_only() -> None:
    scraper = PageScraper(read_pdfs=True)
    assert "application/pdf" in scraper._client.headers["Accept"]
    assert "application/pdf" not in PageScraper()._client.headers["Accept"]
    scraper.close()
    assert scraper._client.is_closed

    class Closable:
        closed = False

        def scrape_many(self, urls, query, focus=()):
            return {}

        def close(self) -> None:
            self.closed = True

    closable = Closable()
    Orchestrator(
        Researcher(FakeLLM([]), FakeSearch([]), scraper=closable),
        Analyst(FakeLLM([])),
        Critic(FakeLLM([])),
    ).close()
    assert closable.closed
    Researcher(FakeLLM([]), FakeSearch([])).close()  # no scraper: nothing to close

    shared = httpx.Client()
    PageScraper(client=shared).close()
    assert not shared.is_closed
    shared.close()


# --- R9: competitor citations are not doubled ---------------------------------------


@pytest.mark.parametrize(
    ("note", "ids", "expected"),
    [
        ("Leads Nepal.", ["F1"], "Leads Nepal. [F1]"),
        ("Leads Nepal [F1].", ["F1"], "Leads Nepal [F1]."),
        ("Leads Nepal [F1].", ["F1", "F3"], "Leads Nepal [F1]. [F3]"),
        ("Leads Nepal.", [], "Leads Nepal."),
    ],
)
def test_competitor_ids_are_added_only_when_missing(note, ids, expected) -> None:
    assert note_with_refs(Competitor(name="Foodmandu", note=note, finding_ids=ids)) == expected


# --- R10: social posts are dropped when enough other sources exist ----------------


def _nepal(url: str) -> SearchResult:
    return SearchResult(title="Nepal", url=url, content="Food delivery in Nepal grows.")


def test_social_posts_are_dropped_when_five_other_sources_exist() -> None:
    others = [_nepal(f"https://news{i}.example.com/a") for i in range(5)]
    results = [_nepal("https://www.facebook.com/groups/expats/1"), *others]
    ranked = rank_results(results, ["Nepal"], limit=10)
    assert [r.url for r, _ in ranked] == [r.url for r in others]


def test_social_posts_are_kept_last_when_sources_are_few() -> None:
    others = [_nepal(f"https://news{i}.example.com/a") for i in range(4)]
    results = [_nepal("https://www.facebook.com/p/1"), *others]
    ranked = rank_results(results, ["Nepal"], limit=10)
    assert ranked[-1][0].url == "https://www.facebook.com/p/1"
    assert len(ranked) == 5
