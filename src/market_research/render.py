"""Render a finished research state as Markdown for display and download."""

from market_research.grounding import cited_ids
from market_research.models import Competitor, ResearchState

SAMPLE_NOTICE = (
    "> **Sample data notice:** some or all findings come from the built-in sample "
    "dataset, not live web search. Treat them as illustrative."
)


def note_with_refs(competitor: Competitor) -> str:
    """The competitor note followed by the finding ids it does not already cite."""
    missing = [i for i in competitor.finding_ids if i not in cited_ids(competitor.note)]
    return f"{competitor.note} [{', '.join(missing)}]" if missing else competitor.note


def brief_to_markdown(state: ResearchState) -> str:
    brief = state.draft
    if brief is None:
        return f"# Research brief: {state.query}\n\nNo brief was produced."

    lines = [f"# Research brief: {state.query}", ""]
    if state.uses_sample_data:
        lines += [SAMPLE_NOTICE, ""]
    if state.notice:
        lines += [f"> **Note:** {state.notice}", ""]

    lines += ["## Summary", "", brief.summary, ""]

    lines += ["## Competitors", ""]
    if brief.competitors:
        for c in brief.competitors:
            lines.append(f"- **{c.name}**: {note_with_refs(c)}")
    else:
        lines.append("- None identified from the available evidence.")
    lines.append("")

    lines += ["## Key observations", ""]
    lines += [f"- {o}" for o in brief.observations] or ["- None."]
    lines.append("")

    lines += ["## Sources", ""]
    lines += [f"- {s}" for s in brief.sources] or ["- No sources were cited."]
    lines.append("")

    lines += ["## Missing information", ""]
    lines += [f"- {m}" for m in brief.missing_information] or ["- None noted."]
    lines.append("")

    critique = state.critique
    status = "approved" if critique and critique.approved else "not approved"
    lines += [
        "---",
        f"_Critic review: {status} after {state.revisions_used} revision(s)._",
    ]
    q = state.quality
    if q is not None:
        lines.append(
            f"_Evidence: {q.findings} findings from {len(q.domains)} source domain(s), "
            f"{q.scraped_pages} read from the full page; {q.cited} cited "
            f"({q.citation_coverage:.0%} coverage)._"
        )
    if critique and not critique.approved and critique.issues:
        lines += ["", "_Open critic notes:_"] + [f"- {i}" for i in critique.issues]
    return "\n".join(lines) + "\n"
