"""Smoke test of the Streamlit page with a scripted model and sample data."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from market_research import pipeline
from market_research.agents import Analyst, Critic, Orchestrator, Researcher
from market_research.llm import FakeLLM
from market_research.search import SampleDataSearch
from tests.conftest import APPROVE

BUILT_WITH: list = []
APP = str(Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py")


@pytest.fixture
def chosen_providers(monkeypatch: pytest.MonkeyPatch, good_brief) -> list[str | None]:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDERS", "bedrock,groq")
    monkeypatch.setenv("GROQ_API_KEYS", "k1,k2,k3")
    chosen: list[str | None] = []

    def fake_build(settings, provider=None):
        chosen.append(provider)
        BUILT_WITH.append(settings)
        llm = FakeLLM([{"queries": ["food delivery Nepal"]}, good_brief, APPROVE])
        return Orchestrator(Researcher(llm, SampleDataSearch()), Analyst(llm), Critic(llm))

    monkeypatch.setattr(pipeline, "build_orchestrator", fake_build)
    BUILT_WITH.clear()
    return chosen


def markdown_text(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


def research(at: AppTest, query: str) -> AppTest:
    at.text_input(key="query_input").input(query)
    return button(at, "Run research").click().run()


def test_landing_page_explains_agents_and_offers_examples(chosen_providers) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    text = markdown_text(at)
    for agent in ("Orchestrator", "Researcher", "Analyst", "Critic"):
        assert f"**{agent}**" in text
    labels = [b.label for b in at.button]
    assert "Analyze the food delivery market in Nepal" in labels
    assert not at.tabs  # no results yet


def test_run_shows_metrics_and_all_result_tabs(chosen_providers) -> None:
    at = research(AppTest.from_file(APP, default_timeout=30).run(), "Food delivery in Nepal")
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Brief", "Evidence", "Quality", "Agent trace", "Export"]

    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Model"] == "Claude"
    assert metrics["Critic"] == "Approved"
    assert metrics["Citation coverage"] == "50%"  # 2 of the 4 sample findings are cited

    text = markdown_text(at)
    for section in ("Summary", "Competitors", "Key observations", "Sources", "Missing"):
        assert f"**{section}" in text
    assert any("sample dataset" in w.value for w in at.warning)
    assert at.dataframe, "evidence table is shown"
    assert any("Every observation cites a real finding" in s.value for s in at.success)
    assert chosen_providers == ["bedrock"]


def test_example_button_runs_immediately(chosen_providers) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    button(at, "Analyze the food delivery market in Nepal").click().run()
    assert not at.exception
    assert at.text_input(key="query_input").value == "Analyze the food delivery market in Nepal"
    assert at.tabs and chosen_providers == ["bedrock"]


def test_history_keeps_earlier_runs_and_reopens_them(chosen_providers) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    research(at, "Food delivery in Nepal")
    research(at, "Nepal food delivery apps")
    history = at.sidebar.radio[1]
    assert len(history.options) == 2
    assert "### Nepal food delivery apps" in markdown_text(at)

    history.set_value(1).run()
    assert not at.exception
    assert "### Food delivery in Nepal" in markdown_text(at)
    assert len(chosen_providers) == 2  # reopening does not call the model again

    button(at, "Clear history").click().run()
    assert not at.tabs


def test_sidebar_controls_reach_the_pipeline(chosen_providers, monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.sidebar.toggle[0].set_value(False)
    at.sidebar.slider[0].set_value(3)
    research(at, "Food delivery in Nepal")
    settings = BUILT_WITH[-1]
    assert settings.scrape_pages is False
    assert settings.max_search_results == 3


def test_model_picker_offers_claude_and_groq(chosen_providers) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert at.sidebar.radio[0].options == ["Claude (AWS Bedrock)", "Groq"]
    at.sidebar.radio[0].set_value("groq")
    research(at, "Nepal food delivery")
    assert chosen_providers == ["groq"]
    assert {m.label: m.value for m in at.metric}["Model"] == "Groq"


def test_blank_query_shows_warning(chosen_providers) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    button(at, "Run research").click().run()
    assert any("Please enter" in w.value for w in at.warning)
