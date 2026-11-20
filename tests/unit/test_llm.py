from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from market_research.config import Settings
from market_research.llm import (
    BedrockClaudeClient,
    FakeLLM,
    FallbackLLM,
    GroqClient,
    KeyRotator,
    LLMError,
    build_llm,
    complete_json,
    extract_json,
)


class RateLimited(Exception):
    status_code = 429

    def __init__(self, retry_after: str | None = None) -> None:
        super().__init__("rate limited")
        self.response = SimpleNamespace(headers={"retry-after": retry_after} if retry_after else {})


class ScriptedGroq:
    """Fake Groq client: pops an outcome per call (exception or text)."""

    def __init__(self, outcomes: list) -> None:
        self.outcomes = outcomes
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **_: object) -> SimpleNamespace:
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        message = SimpleNamespace(content=outcome)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def make_groq(scripts: dict[str, list], sleeps: list[float]) -> GroqClient:
    return GroqClient(
        api_keys=list(scripts),
        model="test-model",
        client_factory=lambda key: ScriptedGroq(scripts[key]),
        sleep=sleeps.append,
    )


def test_key_rotator_cycles_and_rejects_empty() -> None:
    rotator = KeyRotator(["a", " ", "b"])
    assert rotator.key == "a"
    assert rotator.rotate() == "b"
    assert rotator.rotate() == "a"
    with pytest.raises(ValueError):
        KeyRotator(["", "  "])


def test_groq_rotates_to_next_key_on_429_without_waiting() -> None:
    sleeps: list[float] = []
    groq = make_groq({"k1": [RateLimited()], "k2": ["hello"]}, sleeps)
    assert groq.complete("sys", "hi") == "hello"
    assert sleeps == []


def test_groq_waits_retry_after_when_all_keys_limited() -> None:
    sleeps: list[float] = []
    groq = make_groq({"k1": [RateLimited("3"), "ok"], "k2": [RateLimited()]}, sleeps)
    assert groq.complete("sys", "hi") == "ok"
    assert sleeps == [3.0]


def test_groq_gives_up_after_max_rounds() -> None:
    sleeps: list[float] = []
    groq = make_groq({"k1": [RateLimited()] * 3}, sleeps)
    with pytest.raises(LLMError, match="rate limited"):
        groq.complete("sys", "hi")
    assert sleeps == [2.0, 4.0]


def test_groq_non_rate_limit_error_is_not_retried() -> None:
    sleeps: list[float] = []
    groq = make_groq({"k1": [RuntimeError("bad request")], "k2": ["unused"]}, sleeps)
    with pytest.raises(LLMError, match="bad request"):
        groq.complete("sys", "hi")


def test_bedrock_client_joins_text_and_handles_refusal() -> None:
    def response(stop_reason: str, text: str) -> SimpleNamespace:
        return SimpleNamespace(
            stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)]
        )

    replies = [response("end_turn", "brief"), response("refusal", "")]
    fake = SimpleNamespace(messages=SimpleNamespace(create=lambda **_: replies.pop(0)))
    client = BedrockClaudeClient(model_id="m", region="us-east-1", client=fake)
    assert client.complete("sys", "hi") == "brief"
    with pytest.raises(LLMError, match="declined"):
        client.complete("sys", "hi")


def test_fallback_uses_next_provider_when_first_fails() -> None:
    chain = FallbackLLM([FakeLLM([]), FakeLLM(["from second"])])
    assert chain.complete("sys", "hi") == "from second"
    with pytest.raises(LLMError, match="All LLM providers failed"):
        FallbackLLM([FakeLLM([])]).complete("sys", "hi")


class Answer(BaseModel):
    value: int


def test_extract_json_handles_fences_and_prose() -> None:
    assert extract_json('Sure!\n```json\n{"value": 1}\n```') == '{"value": 1}'
    assert extract_json('Here: {"value": 2} done') == '{"value": 2}'


def test_complete_json_retries_once_on_invalid_output() -> None:
    llm = FakeLLM(["not json", '{"value": 7}'])
    assert complete_json(llm, "sys", "give a number", Answer).value == 7
    assert "previous reply was invalid" in llm.calls[1]["prompt"]


def test_complete_json_raises_after_attempts() -> None:
    with pytest.raises(LLMError, match="valid Answer"):
        complete_json(FakeLLM(["nope", "still nope"]), "sys", "p", Answer)


def test_build_llm_skips_groq_without_keys() -> None:
    settings = Settings(_env_file=None, llm_providers="groq", groq_api_keys=None)
    with pytest.raises(LLMError, match="No LLM provider"):
        build_llm(settings)
    settings = Settings(_env_file=None, llm_providers="groq", groq_api_keys="k1, k2")
    chain = build_llm(settings)
    assert chain.name == "Groq llama-3.3-70b-versatile"


def test_bedrock_client_rejects_unknown_api() -> None:
    with pytest.raises(ValueError, match="Unknown Bedrock API"):
        BedrockClaudeClient(model_id="m", region="us-east-1", api="converse")


def test_bedrock_invoke_client_is_default_and_builds_offline() -> None:
    from anthropic import AnthropicBedrock

    client = BedrockClaudeClient(model_id="anthropic.claude-opus-4-6-v1", region="us-east-1")
    assert isinstance(client._client, AnthropicBedrock)
