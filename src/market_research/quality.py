"""Evidence quality of a run, measured in code rather than judged by the model."""

from market_research.grounding import check_grounding, cited_ids
from market_research.models import Brief, QualityReport, ResearchState


def brief_citations(brief: Brief) -> set[str]:
    """Every finding id the brief cites, in the summary, observations or competitors."""
    used = cited_ids(brief.summary)
    for observation in brief.observations:
        used |= cited_ids(observation)
    for competitor in brief.competitors:
        used |= set(competitor.finding_ids)
    return used


def assess(state: ResearchState) -> QualityReport:
    findings = state.findings
    known = {f.id for f in findings}
    cited = brief_citations(state.draft) & known if state.draft else set()
    return QualityReport(
        findings=len(findings),
        cited=len(cited),
        citation_coverage=round(len(cited) / len(findings), 2) if findings else 0.0,
        domains=sorted({f.domain for f in findings if f.domain}),
        scraped_pages=sum(f.evidence == "scraped page" for f in findings),
        search_snippets=sum(f.evidence == "search snippet" for f in findings),
        sample_findings=sum(f.evidence == "sample data" for f in findings),
        on_focus=sum(f.on_focus for f in findings),
        focus=list(state.focus),
        kind=state.kind,
        grounding_problems=check_grounding(state.draft, findings, state.kind)
        if state.draft
        else [],
    )
