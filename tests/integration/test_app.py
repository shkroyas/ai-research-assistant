"""Smoke test of the Streamlit page with a scripted model and sample data."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from market_research import pipeline
from market_research.agents import Analyst, Critic, Orchestrator, Researcher
from market_research.llm import FakeLLM
from market_research.search import SampleDataSearch
from tests.conftest import APPROVE

APP = str(Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py")


@pytest.fixture
def chosen_providers(monkeypatch: pytest.MonkeyPatch, good_brief) -> list[str | None]:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDERS", "bedrock,groq")
    monkeypatch.setenv("GROQ_API_KEYS", "k1,k2,k3")
    chosen: list[str | None] = []

    def fake_build(settings, provider=None):
        chosen.append(provider)
        llm = FakeLLM([{"queries": ["food delivery Nepal"]}, good_brief, APPROVE])
        return Orchestrator(Researcher(llm, SampleDataSearch()), Analyst(llm), Critic(llm))

    monkeypatch.setattr(pipeline, "build_orchestrator", fake_build)
    return chosen


def markdown_text(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def test_page_renders_brief_after_research(chosen_providers) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    at.text_input[0].input("Analyze the food delivery market in Nepal")
    at.button[0].click().run()
    assert not at.exception

    text = markdown_text(at)
    for section in ("Summary", "Competitors", "Key observations", "Sources", "Missing"):
        assert f"**{section}" in text
    assert any("sample dataset" in w.value for w in at.warning)
    assert at.metric[2].value == "Approved"
    assert chosen_providers == ["bedrock"]


def test_model_picker_offers_claude_and_groq(chosen_providers) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert at.radio[0].options == ["Claude (AWS Bedrock)", "Groq"]
    at.radio[0].set_value("groq")
    at.text_input[0].input("Nepal food delivery")
    at.button[0].click().run()
    assert chosen_providers == ["groq"]
    assert at.metric[0].value == "Groq"


def test_blank_query_shows_warning(chosen_providers) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    assert any("Please enter" in w.value for w in at.warning)
