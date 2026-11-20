import pytest

from market_research.agents import Analyst, Critic, Researcher
from market_research.llm import FakeLLM
from market_research.models import Brief, Finding, ResearchState
from market_research.search import SearchResult
from tests.conftest import APPROVE, REJECT, FakeSearch


def test_researcher_numbers_findings_and_dedupes(search_results) -> None:
    search = FakeSearch(search_results)
    llm = FakeLLM([{"queries": ["q1", "q2"]}])
    state = Researcher(llm, search).run(ResearchState(query="Nepal food delivery"))
    assert search.queries == ["q1", "q2"]
    assert [f.id for f in state.findings] == ["F1", "F2"]  # same URLs in both searches
    assert state.findings[0].source_url == "https://a.example"
    assert state.trace[0].detail["queries"] == ["q1", "q2"]


def test_researcher_falls_back_to_raw_query_when_planning_fails() -> None:
    search = FakeSearch([])
    state = Researcher(FakeLLM(["bad", "bad"]), search).run(ResearchState(query="EV in Nepal"))
    assert search.queries == ["EV in Nepal"]
    assert state.findings == []


def test_researcher_keeps_sample_data_label() -> None:
    sample = [SearchResult(title="Sample: x", content="c", is_sample_data=True)]
    state = Researcher(FakeLLM([{"queries": ["q"]}]), FakeSearch(sample)).run(
        ResearchState(query="q")
    )
    assert state.uses_sample_data


def _state_with_findings() -> ResearchState:
    return ResearchState(
        query="Nepal food delivery",
        findings=[
            Finding(id="F1", claim="Foodmandu leads.", source_title="Report A", source_url="u1"),
            Finding(id="F2", claim="Pathao grows.", source_title="Report B", is_sample_data=True),
        ],
    )


def test_analyst_drafts_brief_and_builds_sources_in_code(good_brief) -> None:
    llm = FakeLLM([good_brief])
    state = Analyst(llm).run(_state_with_findings())
    assert state.draft is not None
    assert state.draft.sources == ["[F1] Report A - u1", "[F2] Report B (sample data)"]
    assert "F1: Foodmandu leads." in llm.calls[0]["prompt"]
    assert "[SAMPLE DATA]" in llm.calls[0]["prompt"]


def test_analyst_revision_includes_critic_feedback(good_brief) -> None:
    state = _state_with_findings()
    state.draft = good_brief
    state.critique = REJECT
    llm = FakeLLM([good_brief])
    state = Analyst(llm).run(state)
    assert "Be specific" in llm.calls[0]["prompt"]
    assert state.trace[-1].action == "revised brief"


def test_critic_approves_grounded_brief(good_brief) -> None:
    state = _state_with_findings()
    state.draft = good_brief
    state = Critic(FakeLLM([APPROVE])).run(state)
    assert state.critique is not None and state.critique.approved


def test_critic_overrides_model_approval_when_citations_are_invalid(bad_brief) -> None:
    state = _state_with_findings()
    state.draft = bad_brief
    llm = FakeLLM([APPROVE])
    state = Critic(llm).run(state)
    assert state.critique is not None
    assert state.critique.approved is False
    assert any("F9" in issue for issue in state.critique.issues)
    assert state.critique.revision_request
    assert "Automated citation check" in llm.calls[0]["prompt"]


def test_critic_requires_a_draft() -> None:
    with pytest.raises(ValueError, match="draft"):
        Critic(FakeLLM([])).run(ResearchState(query="q"))


def test_analyst_handles_empty_findings() -> None:
    empty = Brief(summary="No evidence found.", missing_information=["Everything"])
    state = Analyst(FakeLLM([empty])).run(ResearchState(query="q"))
    assert state.draft is not None and state.draft.sources == []
