from market_research.models import Critique, Finding, ResearchState
from market_research.render import SAMPLE_NOTICE, brief_to_markdown


def test_markdown_contains_all_brief_sections(good_brief) -> None:
    state = ResearchState(query="Nepal food delivery", draft=good_brief)
    state.critique = Critique(approved=True)
    md = brief_to_markdown(state)
    for heading in ("## Summary", "## Competitors", "## Key observations", "## Sources"):
        assert heading in md
    assert "## Missing information" in md
    assert "**Foodmandu**" in md
    assert "approved after 0 revision(s)" in md
    assert SAMPLE_NOTICE not in md


def test_markdown_flags_sample_data_and_open_critic_notes(good_brief) -> None:
    state = ResearchState(
        query="q",
        draft=good_brief,
        findings=[Finding(id="F1", claim="c", source_title="t", is_sample_data=True)],
        critique=Critique(approved=False, issues=["Thin evidence"]),
        revisions_used=1,
    )
    md = brief_to_markdown(state)
    assert SAMPLE_NOTICE in md
    assert "not approved after 1 revision(s)" in md
    assert "- Thin evidence" in md


def test_markdown_without_draft() -> None:
    assert "No brief was produced" in brief_to_markdown(ResearchState(query="q"))


def test_markdown_includes_evidence_line_when_quality_is_known(good_brief) -> None:
    from market_research.models import QualityReport, ResearchState
    from market_research.render import brief_to_markdown

    state = ResearchState(
        query="q",
        draft=good_brief,
        quality=QualityReport(
            findings=4, cited=2, citation_coverage=0.5, domains=["a.example"], scraped_pages=3
        ),
    )
    md = brief_to_markdown(state)
    assert (
        "_Evidence: 4 findings from 1 source domain(s), 3 read from the full page; "
        "2 cited (50% coverage)._" in md
    )
