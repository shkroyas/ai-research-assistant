"""Language model clients used by the agents.

All agents talk to an ``LLMClient``: one method, ``complete(system, prompt)``,
returning text. Concrete clients:

* ``BedrockClaudeClient``: Claude through Amazon Bedrock.
* ``GroqClient``: Groq's free tier, rotating across several API keys and
  backing off when every key is rate limited (HTTP 429).
* ``FakeLLM``: scripted responses for offline tests.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised when a model call fails and cannot be retried further."""


# Seconds before a model call gives up, so a stalled request never hangs the app.
REQUEST_TIMEOUT = 120.0


class LLMClient(Protocol):
    name: str

    def complete(self, system: str, prompt: str, max_tokens: int = 4000) -> str: ...


# ---------------------------------------------------------------------------
# Amazon Bedrock (Claude)
# ---------------------------------------------------------------------------


BEDROCK_APIS = ("invoke", "mantle")


class BedrockClaudeClient:
    """Claude on Amazon Bedrock. AWS credentials come from the usual AWS sources
    (environment variables, ``~/.aws/credentials`` or an IAM role).

    ``api="invoke"`` uses Bedrock's InvokeModel endpoint (``bedrock-runtime``),
    which serves Claude Opus 4.6 and earlier as well as newer models.
    ``api="mantle"`` uses Bedrock's Messages-API endpoint for Claude 4.7 and later.
    """

    def __init__(
        self,
        model_id: str,
        region: str,
        aws_profile: str | None = None,
        api: str = "invoke",
        client: Any | None = None,
        temperature: float | None = None,
    ) -> None:
        if api not in BEDROCK_APIS:
            raise ValueError(f"Unknown Bedrock API {api!r}; use one of {BEDROCK_APIS}")
        if client is None:
            if api == "mantle":
                from anthropic import AnthropicBedrockMantle

                client = AnthropicBedrockMantle(
                    aws_region=region, aws_profile=aws_profile, timeout=REQUEST_TIMEOUT
                )
            else:
                from anthropic import AnthropicBedrock

                client = AnthropicBedrock(
                    aws_region=region, aws_profile=aws_profile, timeout=REQUEST_TIMEOUT
                )
        self._client = client
        self.model_id = model_id
        self.name = f"Bedrock {model_id}"
        self.temperature = temperature

    def complete(self, system: str, prompt: str, max_tokens: int = 4000) -> str:
        request: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.temperature is not None:
            request["temperature"] = self.temperature
        try:
            try:
                response = self._client.messages.create(**request)
            except Exception as exc:
                # Newer Claude models reject sampling settings. Drop it for this
                # session and retry once, rather than failing the run.
                if "temperature" not in request or "temperature" not in str(exc).lower():
                    raise
                logger.warning("%s does not accept temperature; using its default", self.name)
                self.temperature = None
                del request["temperature"]
                response = self._client.messages.create(**request)
        except Exception as exc:  # SDK raises typed errors; callers only need "failed"
            raise LLMError(f"{self.name} request failed: {exc}") from exc

        if response.stop_reason == "refusal":
            raise LLMError(f"{self.name} declined the request")
        text = "".join(block.text for block in response.content if block.type == "text")
        if not text.strip():
            raise LLMError(f"{self.name} returned no text")
        return text


# ---------------------------------------------------------------------------
# Groq with key rotation
# ---------------------------------------------------------------------------


class KeyRotator:
    """Round-robin over several API keys, skipping keys marked as disabled."""

    def __init__(self, keys: Sequence[str]) -> None:
        cleaned = [k.strip() for k in keys if k and k.strip()]
        if not cleaned:
            raise ValueError("at least one API key is required")
        self.keys = cleaned
        self.current = 0
        self.disabled: set[int] = set()

    @property
    def key(self) -> str:
        return self.keys[self.current]

    @property
    def active_count(self) -> int:
        return len(self.keys) - len(self.disabled)

    def rotate(self) -> str:
        """Move to the next key that is not disabled."""
        if self.active_count == 0:
            raise LLMError("all API keys are disabled")
        for _ in range(len(self.keys)):
            self.current = (self.current + 1) % len(self.keys)
            if self.current not in self.disabled:
                break
        return self.key

    def disable_current(self) -> None:
        """Stop using the current key (for example after 401 or 403)."""
        self.disabled.add(self.current)


RATE_LIMITED = 429
KEY_REJECTED = (401, 403)


def _status(exc: Exception) -> int | None:
    return getattr(exc, "status_code", None)


def _retry_after_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    value = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


class GroqClient:
    """Groq chat completions with key rotation.

    * 429 (too many requests): switch to the next key at once. When every
      usable key is rate limited in the same round, wait (``retry-after`` if
      Groq sent one, otherwise exponential back-off) and start another round.
    * 401 / 403 (key invalid or forbidden): disable that key for the rest of
      the session and switch to the next one, without waiting.
    * Any other error is raised immediately.
    """

    def __init__(
        self,
        api_keys: Sequence[str],
        model: str,
        max_rounds: int = 3,
        base_delay: float = 2.0,
        client_factory: Callable[[str], Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        temperature: float | None = None,
    ) -> None:
        self.temperature = temperature
        self.rotator = KeyRotator(api_keys)
        self.model = model
        self.max_rounds = max_rounds
        self.base_delay = base_delay
        self._sleep = sleep
        if client_factory is None:
            from groq import Groq

            def client_factory(key: str) -> Any:
                return Groq(api_key=key, max_retries=0, timeout=REQUEST_TIMEOUT)

        self._clients = {key: client_factory(key) for key in self.rotator.keys}
        self.name = f"Groq {model}"

    def _call(self, system: str, prompt: str, max_tokens: int) -> str:
        client = self._clients[self.rotator.key]
        sampling = {} if self.temperature is None else {"temperature": self.temperature}
        response = client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            **sampling,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        text = response.choices[0].message.content or ""
        if not text.strip():
            raise LLMError(f"{self.name} returned no text")
        return text

    def complete(self, system: str, prompt: str, max_tokens: int = 4000) -> str:
        last_error: Exception | None = None
        for round_number in range(self.max_rounds):
            retry_after: float | None = None
            attempts = self.rotator.active_count
            while attempts > 0:
                attempts -= 1
                key_number = self.rotator.current + 1
                try:
                    return self._call(system, prompt, max_tokens)
                except LLMError:
                    raise
                except Exception as exc:
                    status = _status(exc)
                    last_error = exc
                    if status in KEY_REJECTED:
                        logger.warning(
                            "Groq key %d rejected (%s), disabling it", key_number, status
                        )
                        self.rotator.disable_current()
                        if self.rotator.active_count == 0:
                            raise LLMError(
                                f"{self.name}: every API key was rejected (401/403). "
                                "Check GROQ_API_KEYS."
                            ) from exc
                    elif status == RATE_LIMITED:
                        logger.warning("Groq key %d rate limited, rotating", key_number)
                        retry_after = _retry_after_seconds(exc) or retry_after
                    else:
                        raise LLMError(f"{self.name} request failed: {exc}") from exc
                    self.rotator.rotate()
            if round_number < self.max_rounds - 1:
                delay = retry_after or self.base_delay * (2**round_number)
                logger.warning("All Groq keys rate limited, waiting %.1fs", delay)
                self._sleep(delay)
        raise LLMError(
            f"{self.name}: all keys rate limited after {self.max_rounds} rounds"
        ) from last_error


# ---------------------------------------------------------------------------
# Test double
# ---------------------------------------------------------------------------


class FakeLLM:
    """Returns scripted responses in order and records every prompt."""

    name = "Fake LLM"

    def __init__(self, responses: Sequence[str | BaseModel | dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, str]] = []

    def complete(self, system: str, prompt: str, max_tokens: int = 4000) -> str:
        self.calls.append({"system": system, "prompt": prompt})
        if not self._responses:
            raise LLMError("FakeLLM has no responses left")
        item = self._responses.pop(0)
        if isinstance(item, BaseModel):
            return item.model_dump_json()
        if isinstance(item, dict):
            return json.dumps(item)
        return item


# ---------------------------------------------------------------------------
# Structured output helper
# ---------------------------------------------------------------------------

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> str:
    """Pull a JSON object out of a reply that may include code fences or prose."""
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object found in model reply")
    return text[start : end + 1]


def complete_json(
    llm: LLMClient,
    system: str,
    prompt: str,
    schema: type[T],
    max_tokens: int = 4000,
    attempts: int = 2,
) -> T:
    """Ask for JSON matching ``schema``; on invalid output, retry with the error."""
    instructions = (
        f"{prompt}\n\nRespond with a single JSON object only, no prose, matching this "
        f"JSON schema:\n{json.dumps(schema.model_json_schema())}"
    )
    current = instructions
    last_error: Exception | None = None
    for _ in range(attempts):
        reply = llm.complete(system, current, max_tokens)
        try:
            return schema.model_validate_json(extract_json(reply))
        except (ValueError, ValidationError) as exc:
            last_error = exc
            current = (
                f"{instructions}\n\nYour previous reply was invalid: {exc}. "
                "Return corrected JSON only."
            )
    raise LLMError(f"Model did not return valid {schema.__name__}: {last_error}")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


PROVIDER_LABELS = {"bedrock": "Claude (AWS Bedrock)", "groq": "Groq"}


def available_providers(settings: Any) -> list[str]:
    """Providers the user can pick, in configured order. Groq needs at least one key."""
    return [p for p in settings.provider_order if p != "groq" or settings.groq_key_list]


def build_llm(settings: Any, provider: str | None = None) -> LLMClient:
    """Build the client for the chosen provider (default: the first available one)."""
    choices = available_providers(settings)
    if not choices:
        raise LLMError("No LLM provider is configured. See .env.example.")
    provider = provider or choices[0]
    if provider not in choices:
        raise LLMError(f"Provider {provider!r} is not configured. Available: {', '.join(choices)}")
    if provider == "bedrock":
        return BedrockClaudeClient(
            model_id=settings.bedrock_model_id,
            region=settings.aws_region,
            aws_profile=settings.aws_profile,
            api=settings.bedrock_api,
            temperature=settings.llm_temperature,
        )
    return GroqClient(
        api_keys=settings.groq_key_list,
        model=settings.groq_model,
        temperature=settings.llm_temperature,
    )
