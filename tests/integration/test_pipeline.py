"""End-to-end runs of the four agents with a scripted model, fully offline."""

from market_research.agents import Analyst, Critic, Orchestrator, Researcher
from market_research.llm import FakeLLM
from market_research.search import SampleDataSearch
from tests.conftest import APPROVE, REJECT, FakeSearch


def build(llm: FakeLLM, search) -> Orchestrator:
    return Orchestrator(Researcher(llm, search), Analyst(llm), Critic(llm), max_revisions=1)


def test_happy_path_runs_roles_in_order(search_results, good_brief) -> None:
    llm = FakeLLM([{"queries": ["q"]}, good_brief, APPROVE])
    steps: list[str] = []
    state = build(llm, FakeSearch(search_results)).run(
        "Analyze the food delivery market in Nepal", on_step=lambda agent, _: steps.append(agent)
    )
    assert steps == ["Orchestrator", "Researcher", "Analyst", "Critic", "Orchestrator"]
    assert state.critique is not None and state.critique.approved
    assert state.revisions_used == 0
    assert [t.agent for t in state.trace] == [
        "Orchestrator",
        "Researcher",
        "Researcher",
        "Analyst",
        "Critic",
        "Orchestrator",
    ]


def test_one_revision_then_approval(search_results, good_brief) -> None:
    llm = FakeLLM([{"queries": ["q"]}, good_brief, REJECT, good_brief, APPROVE])
    state = build(llm, FakeSearch(search_results)).run("Nepal food delivery")
    assert state.revisions_used == 1
    assert state.critique is not None and state.critique.approved


def test_never_more_than_one_revision(search_results, good_brief) -> None:
    llm = FakeLLM([{"queries": ["q"]}, good_brief, REJECT, good_brief, REJECT])
    state = build(llm, FakeSearch(search_results)).run("Nepal food delivery")
    assert state.revisions_used == 1
    assert state.critique is not None and not state.critique.approved
    assert state.trace[-1].detail == {
        "approved": False,
        "revisions_used": 1,
        "citation_coverage": 1.0,
    }
    assert llm.calls and len(llm.calls) == 5  # no sixth model call


def test_offline_run_with_labelled_sample_data(good_brief) -> None:
    llm = FakeLLM([{"queries": ["food delivery Nepal"]}, good_brief, APPROVE])
    state = build(llm, SampleDataSearch()).run("Analyze the food delivery market in Nepal")
    assert state.findings and state.uses_sample_data
    assert state.draft is not None
    assert all("(sample data)" in s for s in state.draft.sources)
