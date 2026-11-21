"""The research-brief command, run offline with a scripted model and sample data."""

import json

import pytest

from market_research import cli, pipeline
from market_research.agents import Analyst, Critic, Orchestrator, Researcher
from market_research.llm import FakeLLM, LLMError
from market_research.search import SampleDataSearch
from tests.conftest import APPROVE


@pytest.mark.parametrize(
    ("query", "slug"),
    [
        ("Analyze the food delivery market in Nepal", "food-delivery-nepal"),
        ("Tesla", "tesla"),
        ("The market", "the-market"),
        ("???", "research-brief"),
    ],
)
def test_slugify(query: str, slug: str) -> None:
    assert cli.slugify(query) == slug


@pytest.fixture
def chosen(monkeypatch: pytest.MonkeyPatch, good_brief) -> list[str | None]:
    monkeypatch.setenv("GROQ_API_KEYS", "k1")
    providers: list[str | None] = []

    def fake_build(settings, provider=None):
        providers.append(provider)
        llm = FakeLLM([{"queries": ["food delivery Nepal"]}, good_brief, APPROVE])
        return Orchestrator(Researcher(llm, SampleDataSearch()), Analyst(llm), Critic(llm))

    monkeypatch.setattr(pipeline, "build_orchestrator", fake_build)
    return providers


def test_writes_markdown_and_json(chosen, tmp_path, capsys) -> None:
    code = cli.main(
        ["Analyze the food delivery market in Nepal", "--provider", "groq", "--out", str(tmp_path)]
    )
    assert code == 0
    assert chosen == ["groq"]

    md = (tmp_path / "food-delivery-nepal.md").read_text()
    assert md.startswith("# Research brief: Analyze the food delivery market in Nepal")
    assert "## Missing information" in md

    run = json.loads((tmp_path / "food-delivery-nepal.json").read_text())
    assert run["critique"]["approved"] is True
    assert run["findings"] and all(f["is_sample_data"] for f in run["findings"])

    out, err = capsys.readouterr()
    assert out.splitlines() == [
        str(tmp_path / "food-delivery-nepal.md"),
        str(tmp_path / "food-delivery-nepal.json"),
    ]
    assert "Critic:" in err


def test_name_overrides_slug(chosen, tmp_path) -> None:
    assert cli.main(["Nepal food delivery", "--out", str(tmp_path), "--name", "demo"]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["demo.json", "demo.md"]


def test_model_failure_exits_1_and_writes_nothing(monkeypatch, tmp_path, capsys) -> None:
    def failing_build(settings, provider=None):
        raise LLMError("every API key was rejected")

    monkeypatch.setattr(pipeline, "build_orchestrator", failing_build)
    assert cli.main(["Nepal food delivery", "--out", str(tmp_path / "out")]) == 1
    assert not (tmp_path / "out").exists()
    assert "error: every API key was rejected" in capsys.readouterr().err
