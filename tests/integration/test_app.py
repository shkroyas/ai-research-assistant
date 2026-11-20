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
def offline_pipeline(monkeypatch: pytest.MonkeyPatch, good_brief) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    def fake_build(settings):
        llm = FakeLLM([{"queries": ["food delivery Nepal"]}, good_brief, APPROVE])
        return Orchestrator(Researcher(llm, SampleDataSearch()), Analyst(llm), Critic(llm))

    monkeypatch.setattr(pipeline, "build_orchestrator", fake_build)


def test_page_renders_brief_after_research(offline_pipeline) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    at.text_input[0].input("Analyze the food delivery market in Nepal")
    at.button[0].click().run()
    assert not at.exception

    subheaders = [s.value for s in at.subheader]
    for section in ("Summary", "Competitors", "Key observations", "Sources"):
        assert section in subheaders
    assert any("Sample data" in w.value for w in at.warning)
    assert any("Approved by the Critic" in s.value for s in at.success)


def test_blank_query_shows_warning(offline_pipeline) -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    assert any("Please enter" in w.value for w in at.warning)
