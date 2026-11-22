"""Fixes for problems seen in live runs on Claude and Groq (spec 010)."""

import pytest

from market_research.agents import Researcher
from market_research.evidence import clean_evidence, is_social, rank_results, settle_kind
from market_research.grounding import check_grounding
from market_research.llm import FakeLLM
from market_research.models import Brief, Competitor, Finding, ResearchState
from market_research.prompts import RESEARCHER_SYSTEM
from market_research.search import SearchResult
from tests.conftest import FakeSearch


def test_single_company_request_is_not_a_comparison() -> None:
    # Groq classed this as a comparison and put Tesla's rivals into the focus.
    query = "Research Tesla and its main competitors"
    assert settle_kind(query, "comparison", ["Tesla", "BYD", "Volkswagen"]) == (
        "company",
        ["Tesla"],
    )


@pytest.mark.parametrize(
    ("query", "kind", "focus", "expected"),
    [
        (
            "Compare eSewa and Khalti",
            "comparison",
            ["eSewa", "Khalti"],
            ("comparison", ["eSewa", "Khalti"]),
        ),
        ("Swiggy vs Zomato", "comparison", ["Swiggy"], ("comparison", ["Swiggy"])),
        (
            "Food delivery in Nepal",
            "market",
            ["Nepal", "Kathmandu"],
            ("market", ["Nepal", "Kathmandu"]),
        ),
    ],
)
def test_other_requests_keep_their_type_and_focus(query, kind, focus, expected) -> None:
    assert settle_kind(query, kind, focus) == expected


def test_researcher_applies_the_correction() -> None:
    plan = {"kind": "comparison", "focus": ["Tesla", "BYD"], "queries": ["Tesla rivals"]}
    search = FakeSearch([])
    state = Researcher(FakeLLM([plan]), search).run(
        ResearchState(query="Research Tesla and its main competitors")
    )
    assert (state.kind, state.focus) == ("company", ["Tesla"])


def test_company_cannot_be_its_own_competitor() -> None:
    findings = [Finding(id="F1", claim="Tesla and BYD lead EV sales", source_title="A")]
    brief = Brief(
        summary="s [F1]",
        observations=["o [F1]"],
        competitors=[Competitor(name="Tesla", note="focus company", finding_ids=["F1"])],
    )
    problems = check_grounding(brief, findings, "company", ["Tesla"])
    assert problems == [
        "Competitor 'Tesla' is the company being researched; name its rivals instead"
    ]


def test_page_noise_is_removed() -> None:
    header = (
        "Rank Company Details Short Description Total Funding Investors Founded Year "
        "Location Stage Employees Revenue Valuation Category Tags"
    )
    assert clean_evidence(header) == ""
    assert clean_evidence("arrow_forward 🍔🍟 Foodmandu delivers in Kathmandu.") == (
        "Foodmandu delivers in Kathmandu."
    )


def test_social_posts_rank_after_other_sources() -> None:
    def result(url: str) -> SearchResult:
        return SearchResult(title="Nepal", url=url, content="Food delivery in Nepal grows.")

    results = [result("https://www.facebook.com/p/1"), result("https://kathmandupost.com/a")]
    ranked = rank_results(results, ["Nepal"], limit=5)
    assert [r.url for r, _ in ranked] == [
        "https://kathmandupost.com/a",
        "https://www.facebook.com/p/1",
    ]
    assert is_social("https://instagram.com/p/x") and not is_social("https://x.company.com/a")


def test_prompt_keeps_rivals_out_of_the_focus_and_asks_for_a_clear_decline_reason() -> None:
    assert "Never add their" in RESEARCHER_SYSTEM and "rivals to the focus" in RESEARCHER_SYSTEM
    assert "not business research" in RESEARCHER_SYSTEM
