"""Low model temperature for consistent runs, with a safe fallback (spec 009)."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from market_research.config import Settings
from market_research.llm import BedrockClaudeClient, GroqClient, build_llm
from market_research.prompts import ANALYST_SYSTEM


def reply(text: str = "ok") -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)]
    )


def test_bedrock_sends_the_configured_temperature() -> None:
    calls: list[dict] = []
    fake = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: calls.append(kw) or reply())
    )
    BedrockClaudeClient(model_id="m", region="r", client=fake, temperature=0.2).complete("s", "p")
    assert calls[0]["temperature"] == 0.2


def test_models_that_reject_temperature_fall_back_to_their_default() -> None:
    calls: list[dict] = []

    def create(**kw):
        calls.append(kw)
        if "temperature" in kw:
            raise ValueError("400: temperature is not supported for this model")
        return reply("brief")

    client = BedrockClaudeClient(
        model_id="rejects-temperature",
        region="r",
        client=SimpleNamespace(messages=SimpleNamespace(create=create)),
        temperature=0.2,
    )
    assert client.complete("s", "p") == "brief"
    assert client.complete("s", "p") == "brief"
    assert ["temperature" in c for c in calls] == [True, False, False]  # remembered
    fresh = BedrockClaudeClient(
        model_id="rejects-temperature", region="r", client=client._client, temperature=0.2
    )
    assert fresh.temperature is None  # later runs in the same app skip it at once


def test_groq_sends_the_configured_temperature() -> None:
    seen: list[dict] = []

    def create(**kw):
        seen.append(kw)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    GroqClient(["k"], "m", client_factory=lambda key: fake, temperature=0.2).complete("s", "p")
    assert seen[0]["temperature"] == 0.2


def test_temperature_defaults_low_but_not_zero_and_is_validated() -> None:
    settings = Settings(_env_file=None, llm_providers="groq", groq_api_keys="k")
    assert settings.llm_temperature == 0.2
    assert build_llm(settings, "groq").temperature == 0.2
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_temperature=1.5)


def test_analyst_picks_competitors_by_how_often_the_findings_mention_them() -> None:
    assert "the most findings mention" in ANALYST_SYSTEM
