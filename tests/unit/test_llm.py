from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from market_research.config import Settings
from market_research.llm import (
    BedrockClaudeClient,
    FakeLLM,
    GroqClient,
    KeyRotator,
    LLMError,
    available_providers,
    build_llm,
    complete_json,
    extract_json,
)


class RateLimited(Exception):
    status_code = 429

    def __init__(self, retry_after: str | None = None) -> None:
        super().__init__("rate limited")
        self.response = SimpleNamespace(headers={"retry-after": retry_after} if retry_after else {})


class KeyRejected(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


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
    rotator.disable_current()
    assert rotator.rotate() == "b"
    assert rotator.rotate() == "b"  # "a" is skipped
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


@pytest.mark.parametrize("status", [401, 403])
def test_groq_disables_rejected_key_and_rotates_without_waiting(status: int) -> None:
    sleeps: list[float] = []
    groq = make_groq({"k1": [KeyRejected(status)], "k2": ["ok", "again"]}, sleeps)
    assert groq.complete("sys", "hi") == "ok"
    assert groq.complete("sys", "hi") == "again"  # k1 is not tried again
    assert sleeps == []
    assert groq.rotator.disabled == {0}


def test_groq_fails_clearly_when_every_key_is_rejected() -> None:
    groq = make_groq({"k1": [KeyRejected(401)], "k2": [KeyRejected(403)]}, [])
    with pytest.raises(LLMError, match="every API key was rejected"):
        groq.complete("sys", "hi")


def test_groq_mixed_rejected_and_rate_limited_keys() -> None:
    sleeps: list[float] = []
    groq = make_groq({"k1": [KeyRejected(401)], "k2": [RateLimited(), "ok"]}, sleeps)
    assert groq.complete("sys", "hi") == "ok"
    assert sleeps == [2.0]  # waited once, only for the rate limit


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


def test_groq_is_only_offered_with_keys() -> None:
    without = Settings(_env_file=None, llm_providers="bedrock,groq", groq_api_keys=None)
    assert available_providers(without) == ["bedrock"]
    with_keys = Settings(_env_file=None, llm_providers="bedrock,groq", groq_api_keys="k1,k2")
    assert available_providers(with_keys) == ["bedrock", "groq"]


def test_build_llm_returns_the_chosen_provider() -> None:
    settings = Settings(_env_file=None, llm_providers="bedrock,groq", groq_api_keys="k1, k2")
    assert isinstance(build_llm(settings), BedrockClaudeClient)  # first is the default
    groq = build_llm(settings, "groq")
    assert isinstance(groq, GroqClient)
    assert groq.rotator.keys == ["k1", "k2"]


def test_build_llm_rejects_unconfigured_provider() -> None:
    settings = Settings(_env_file=None, llm_providers="groq", groq_api_keys=None)
    with pytest.raises(LLMError, match="No LLM provider"):
        build_llm(settings)
    settings = Settings(_env_file=None, llm_providers="bedrock")
    with pytest.raises(LLMError, match="not configured"):
        build_llm(settings, "groq")


def test_bedrock_client_rejects_unknown_api() -> None:
    with pytest.raises(ValueError, match="Unknown Bedrock API"):
        BedrockClaudeClient(model_id="m", region="us-east-1", api="converse")


def test_bedrock_invoke_client_is_default_and_builds_offline() -> None:
    from anthropic import AnthropicBedrock

    client = BedrockClaudeClient(model_id="anthropic.claude-opus-4-6-v1", region="us-east-1")
    assert isinstance(client._client, AnthropicBedrock)
