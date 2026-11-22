"""Evidence cleaning, focus matching and ranking."""

import pytest

from market_research.evidence import (
    clean_evidence,
    ensure_focus,
    fallback_focus,
    mentions_focus,
    rank_results,
)
from market_research.search import SearchResult


def test_clean_evidence_drops_masked_sentences() -> None:
    text = (
        "Revenue in Nepal is projected to reach US$ ****** million in ****. "
        "Foodmandu leads the market in Kathmandu."
    )
    assert clean_evidence(text) == "Foodmandu leads the market in Kathmandu."


def test_clean_evidence_strips_tables_headings_and_symbols() -> None:
    text = "## Key Attributes | | --- | --- | Report | Details | ▲ Growth target 9.4% CAGR."
    cleaned = clean_evidence(text)
    assert "|" not in cleaned and "---" not in cleaned and "#" not in cleaned
    assert "▲" not in cleaned
    assert cleaned.endswith("Growth target 9.4% CAGR.")


def test_clean_evidence_can_leave_nothing() -> None:
    assert clean_evidence("Market size: US$ **** in ****.") == ""


@pytest.mark.parametrize(
    ("query", "focus"),
    [
        ("Analyze the food delivery market in Nepal", ["Nepal"]),
        ("Electric vehicle market in India", ["Electric", "India"]),
        ("Research Tesla", ["Tesla"]),
        ("fintech wallets", []),
    ],
)
def test_fallback_focus_takes_capitalised_names(query: str, focus: list[str]) -> None:
    assert fallback_focus(query) == focus


def test_mentions_focus_is_whole_word_and_case_insensitive() -> None:
    assert mentions_focus(["Food delivery in NEPAL grows"], ["Nepal"])
    assert mentions_focus([None, "https://kathmandupost.com/nepal-delivery"], ["Nepal"])
    assert not mentions_focus(["Nepalese cuisine abroad"], ["Nepal"])
    assert not mentions_focus(["DoorDash leads the US market"], ["Nepal"])
    assert mentions_focus(["anything"], [])


def test_ensure_focus_appends_missing_focus() -> None:
    queries = ["food delivery Nepal market size", "top food delivery apps 2025"]
    assert ensure_focus(queries, ["Nepal"]) == [
        "food delivery Nepal market size",
        "top food delivery apps 2025 Nepal",
    ]
    assert ensure_focus(queries, []) == queries


def test_rank_results_puts_focus_first_and_caps_background() -> None:
    def result(title: str) -> SearchResult:
        return SearchResult(title=title, url=f"https://x.example/{title}", content=title)

    results = [
        result(t) for t in ["global1", "Nepal a", "global2", "global3", "Nepal b", "global4"]
    ]
    ranked = rank_results(results, ["Nepal"], limit=10, max_background=2)
    assert [(r.title, on) for r, on in ranked] == [
        ("Nepal a", True),
        ("Nepal b", True),
        ("global1", False),
        ("global2", False),
    ]
    assert len(rank_results(results, ["Nepal"], limit=3)) == 3
