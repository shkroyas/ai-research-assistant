"""Analyst: writes the brief from the findings, and revises it once if asked."""

from market_research.llm import LLMClient, complete_json
from market_research.models import Brief, Finding, ResearchState
from market_research.prompts import ANALYST_SYSTEM
from market_research.quality import brief_citations


def format_findings(findings: list[Finding]) -> str:
    if not findings:
        return "(no findings were found)"
    lines = []
    for f in findings:
        label = " [SAMPLE DATA]" if f.is_sample_data else ""
        if not f.on_focus:
            label += " [BACKGROUND]"
        source = f.source_url or "no URL"
        lines.append(f"{f.id}{label}: {f.claim}\n    Source: {f.source_title} ({source})")
    return "\n".join(lines)


def focus_line(state: ResearchState) -> str:
    focus = ", ".join(state.focus) if state.focus else "(none named)"
    return f"Focus: {focus}"


def build_sources(brief: Brief, findings: list[Finding]) -> list[str]:
    """List the findings the brief actually cites, in id order, built in code."""
    used = brief_citations(brief)
    sources = []
    for f in findings:
        if f.id in used:
            label = " (sample data)" if f.is_sample_data else ""
            url = f" - {f.source_url}" if f.source_url else ""
            sources.append(f"[{f.id}] {f.source_title}{url}{label}")
    return sources


class Analyst:
    name = "Analyst"

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def run(self, state: ResearchState) -> ResearchState:
        revising = state.critique is not None and not state.critique.approved
        prompt = (
            f"User request: {state.query}\n{focus_line(state)}"
            f"\n\nFindings:\n{format_findings(state.findings)}"
        )
        if revising and state.draft is not None and state.critique is not None:
            prompt += (
                f"\n\nYour previous draft:\n{state.draft.model_dump_json(indent=2)}"
                f"\n\nCritic feedback to address:\n{state.critique.revision_request or ''}"
                f"\nIssues: {'; '.join(state.critique.issues)}"
            )

        brief = complete_json(self.llm, ANALYST_SYSTEM, prompt, Brief)
        brief.sources = build_sources(brief, state.findings)
        state.draft = brief
        state.log(
            self.name,
            "revised brief" if revising else "drafted brief",
            observations=len(brief.observations),
            competitors=[c.name for c in brief.competitors],
        )
        return state
