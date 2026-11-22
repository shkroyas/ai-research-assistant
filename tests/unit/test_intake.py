"""Unclear and inappropriate requests are caught before any research (spec 007)."""

import pytest

from market_research.agents import Analyst, Critic, Orchestrator, Researcher
from market_research.agents.researcher import SearchPlan
from market_research.cli import main as cli_main
from market_research.intake import screen_query
from market_research.llm import FakeLLM
from tests.conftest import FakeSearch


@pytest.mark.parametrize(
    "query", ["hi", "market", "Tell me about the best company", "?!", "x" * 401]
)
def test_rules_catch_requests_with_no_subject(query: str) -> None:
    intake = screen_query(query)
    assert intake is not None and intake.status == "unclear"
    assert intake.question and intake.suggestions


@pytest.mark.parametrize(
    "query", ["Tesla", "EV market", "Analyze the food delivery market in Nepal"]
)
def test_rules_let_real_requests_through(query: str) -> None:
    assert screen_query(query) is None


def test_unknown_status_never_blocks_research() -> None:
    plan = SearchPlan(status="maybe", suggestions=["a", "b", "c", "d", " "], queries=["q"])
    assert plan.status == "research" and plan.suggestions == ["a", "b", "c"]


def pipeline_with(plan: dict) -> tuple[Orchestrator, FakeSearch, FakeLLM]:
    llm = FakeLLM([plan])
    search = FakeSearch([])
    return Orchestrator(Researcher(llm, search), Analyst(llm), Critic(llm)), search, llm


def test_unclear_request_asks_a_question_and_writes_no_brief() -> None:
    orchestrator, search, llm = pipeline_with(
        {
            "status": "unclear",
            "reason": "Mercury could be a bank, a planet or a car brand.",
            "question": "Do you mean Mercury the US fintech bank?",
            "suggestions": ["Research Mercury, the US business bank"],
        }
    )
    state = orchestrator.run("Research Mercury")
    assert state.intake.status == "unclear"
    assert state.intake.question == "Do you mean Mercury the US fintech bank?"
    assert state.draft is None and state.findings == []
    assert search.queries == [] and len(llm.calls) == 1  # no search, no Analyst, no Critic
    assert [t.action for t in state.trace][-2:] == [
        "asked for clarification",
        "stopped before research",
    ]


def test_inappropriate_request_is_declined_with_a_reason() -> None:
    orchestrator, search, _ = pipeline_with(
        {"status": "decline", "reason": "This asks for a private person's home address."}
    )
    state = orchestrator.run("Find the home address of the CEO of Foodmandu")
    assert state.intake.status == "decline" and "private" in state.intake.reason
    assert state.draft is None and search.queries == []


def test_rules_stop_vague_requests_without_a_model_call() -> None:
    orchestrator, _, llm = pipeline_with({"queries": ["unused"]})
    state = orchestrator.run("hello")
    assert state.intake.status == "unclear" and llm.calls == []
    assert state.trace[1].detail["checked_by"] == "rules"


def test_cli_explains_and_exits_2_for_unclear_requests(monkeypatch, tmp_path, capsys) -> None:
    from market_research import pipeline

    monkeypatch.setattr(
        pipeline, "build_orchestrator", lambda settings, provider=None: pipeline_with({})[0]
    )
    assert cli_main(["hello", "--out", str(tmp_path)]) == 2
    assert "needs clarifying" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []
