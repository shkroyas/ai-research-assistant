"""Different kinds of requests: market, company, comparison and topic (spec 006)."""

import pytest

from market_research.agents import Researcher
from market_research.agents.researcher import SearchPlan
from market_research.evidence import clean_focus, fallback_kind
from market_research.grounding import check_grounding
from market_research.llm import FakeLLM
from market_research.models import Brief, Competitor, Finding, ResearchState
from market_research.search import SearchResult
from tests.conftest import FakeSearch


def test_unknown_kind_becomes_market() -> None:
    assert SearchPlan(kind="industry report", queries=["q"]).kind == "market"
    assert SearchPlan(kind=None, queries=["q"]).kind == "market"
    assert SearchPlan(kind=" Company ", queries=["q"]).kind == "company"


@pytest.mark.parametrize(
    ("query", "kind"),
    [
        ("Compare eSewa and Khalti", "comparison"),
        ("Swiggy vs Zomato", "comparison"),
        ("Uber versus Lyft in the US", "comparison"),
        ("Food delivery in Nepal", "market"),
    ],
)
def test_fallback_kind_spots_comparisons(query: str, kind: str) -> None:
    assert fallback_kind(query) == kind


def test_clean_focus_drops_global_words() -> None:
    assert clean_focus(["Global", " worldwide ", "Nepal", "nepal", ""]) == ["Nepal"]


def test_plan_keeps_model_kind_and_focus() -> None:
    llm = FakeLLM([{"kind": "company", "focus": ["Tesla"], "queries": ["Tesla revenue 2025"]}])
    state = Researcher(llm, FakeSearch([])).run(ResearchState(query="Research Tesla"))
    assert (state.kind, state.focus) == ("company", ["Tesla"])
    assert state.trace[0].detail["kind"] == "company"
    assert "comparison" in llm.calls[0]["system"]  # type guidance reaches the model


def test_failed_plan_still_detects_a_comparison() -> None:
    state = Researcher(FakeLLM(["bad", "bad"]), FakeSearch([])).run(
        ResearchState(query="Compare eSewa vs Khalti")
    )
    assert state.kind == "comparison"


def test_global_request_has_no_background() -> None:
    results = [
        SearchResult(title="Report", url="https://r.example/1", content="Batteries grew 30%."),
        SearchResult(title="News", url="https://n.example/1", content="CATL leads supply."),
    ]
    llm = FakeLLM([{"kind": "market", "focus": ["global"], "queries": ["EV battery market"]}])
    search = FakeSearch(results)
    state = Researcher(llm, search).run(ResearchState(query="global EV battery market"))
    assert state.focus == []
    assert search.queries == ["EV battery market"]  # nothing appended
    assert all(f.on_focus for f in state.findings)


def test_company_requests_allow_rivals_from_their_own_findings() -> None:
    findings = [
        Finding(id="F1", claim="Tesla sold 1.8M cars", source_title="A"),
        Finding(id="F2", claim="BYD overtook rivals in 2025", source_title="B", on_focus=False),
    ]
    brief = Brief(
        summary="Tesla leads [F1].",
        observations=["Tesla sales [F1]"],
        competitors=[Competitor(name="BYD", note="rival", finding_ids=["F2"])],
    )
    assert check_grounding(brief, findings, "company") == []
    assert check_grounding(brief, findings, "comparison") == []
    assert len(check_grounding(brief, findings, "market")) == 1
