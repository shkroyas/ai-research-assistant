"""Quality report and step timings, computed in code."""

from market_research.agents import Analyst, Critic, Orchestrator, Researcher
from market_research.llm import FakeLLM
from market_research.models import Brief, Finding, ResearchState
from market_research.quality import assess, brief_citations
from tests.conftest import APPROVE, FakeSearch


def findings() -> list[Finding]:
    return [
        Finding(
            id="F1",
            claim="a",
            source_title="A",
            source_url="https://www.a.example/1",
            evidence="scraped page",
        ),
        Finding(id="F2", claim="b", source_title="B", source_url="https://a.example/2"),
        Finding(id="F3", claim="c", source_title="C", source_url="https://c.example/3"),
        Finding(id="F4", claim="d", source_title="D", is_sample_data=True, evidence="sample data"),
    ]


def test_brief_citations_cover_summary_observations_and_competitors(good_brief) -> None:
    assert brief_citations(good_brief) == {"F1", "F2"}


def test_assess_counts_coverage_domains_and_evidence_types(good_brief) -> None:
    state = ResearchState(query="q", findings=findings(), draft=good_brief)
    report = assess(state)
    assert (report.findings, report.cited, report.citation_coverage) == (4, 2, 0.5)
    assert report.domains == ["a.example", "c.example"]
    assert (report.scraped_pages, report.search_snippets, report.sample_findings) == (1, 2, 1)
    assert report.grounding_problems == []


def test_assess_ignores_invented_ids_and_reports_problems() -> None:
    brief = Brief(summary="x [F9]", observations=["claim [F1]", "uncited claim"])
    report = assess(ResearchState(query="q", findings=findings(), draft=brief))
    assert report.cited == 1  # F9 does not exist, so it is not counted
    assert len(report.grounding_problems) == 2


def test_assess_without_draft_or_findings() -> None:
    report = assess(ResearchState(query="q"))
    assert (report.findings, report.cited, report.citation_coverage) == (0, 0, 0.0)


def test_orchestrator_records_step_durations_and_quality(search_results, good_brief) -> None:
    llm = FakeLLM([{"queries": ["q"]}, good_brief, APPROVE])
    orchestrator = Orchestrator(
        Researcher(llm, FakeSearch(search_results)), Analyst(llm), Critic(llm)
    )
    state = orchestrator.run("Nepal food delivery")

    timed = {t.agent for t in state.trace if t.duration_ms is not None}
    assert timed == {"Researcher", "Analyst", "Critic", "Orchestrator"}
    assert state.duration_ms is not None and state.duration_ms >= 0
    assert state.quality is not None and state.quality.citation_coverage == 1.0
    assert state.trace[-1].detail["citation_coverage"] == 1.0


def test_assess_counts_findings_about_the_focus() -> None:
    items = findings()
    items[1].on_focus = False
    state = ResearchState(query="q", findings=items, focus=["Nepal"])
    report = assess(state)
    assert (report.on_focus, report.focus) == (3, ["Nepal"])
