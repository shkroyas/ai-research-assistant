"""Language model clients used by the agents.

All agents talk to an ``LLMClient``: one method, ``complete(system, prompt)``,
returning text. Concrete clients:

* ``BedrockClaudeClient``: Claude through Amazon Bedrock (primary).
* ``GroqClient``: Groq's free tier, rotating across several API keys and
  backing off when every key is rate limited (HTTP 429).
* ``FallbackLLM``: tries clients in order, e.g. Bedrock first, then Groq.
* ``FakeLLM``: scripted responses for offline tests.
"""

from __future__ import annotations

import itertools
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


class LLMClient(Protocol):
    name: str

    def complete(self, system: str, prompt: str, max_tokens: int = 4000) -> str: ...


# ---------------------------------------------------------------------------
# Amazon Bedrock (Claude)
# ---------------------------------------------------------------------------


class BedrockClaudeClient:
    """Claude on Amazon Bedrock. AWS credentials come from the usual AWS sources
    (environment variables, ``~/.aws/credentials`` or an IAM role)."""

    def __init__(
        self,
        model_id: str,
        region: str,
        aws_profile: str | None = None,
        client: Any | None = None,
    ) -> None:
        if client is None:
            from anthropic import AnthropicBedrockMantle

            client = AnthropicBedrockMantle(aws_region=region, aws_profile=aws_profile)
        self._client = client
        self.model_id = model_id
        self.name = f"Bedrock {model_id}"

    def complete(self, system: str, prompt: str, max_tokens: int = 4000) -> str:
        try:
            response = self._client.messages.create(
                model=self.model_id,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
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
    """Round-robin over several API keys."""

    def __init__(self, keys: Sequence[str]) -> None:
        cleaned = [k.strip() for k in keys if k and k.strip()]
        if not cleaned:
            raise ValueError("at least one API key is required")
        self.keys = cleaned
        self._cycle = itertools.cycle(range(len(cleaned)))
        self.current = next(self._cycle)

    @property
    def key(self) -> str:
        return self.keys[self.current]

    def rotate(self) -> str:
        self.current = next(self._cycle)
        return self.key


def _is_rate_limit(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 429


def _retry_after_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    value = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


class GroqClient:
    """Groq chat completions with key rotation and 429 back-off.

    On a 429 the next key is tried immediately. When every key has been rate
    limited in the same round, the client waits (``retry-after`` if Groq sent
    one, otherwise exponential back-off) and starts another round.
    """

    def __init__(
        self,
        api_keys: Sequence[str],
        model: str,
        max_rounds: int = 3,
        base_delay: float = 2.0,
        client_factory: Callable[[str], Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.rotator = KeyRotator(api_keys)
        self.model = model
        self.max_rounds = max_rounds
        self.base_delay = base_delay
        self._sleep = sleep
        if client_factory is None:
            from groq import Groq

            def client_factory(key: str) -> Any:
                return Groq(api_key=key, max_retries=0)

        self._clients = {key: client_factory(key) for key in self.rotator.keys}
        self.name = f"Groq {model}"

    def complete(self, system: str, prompt: str, max_tokens: int = 4000) -> str:
        last_error: Exception | None = None
        for round_number in range(self.max_rounds):
            retry_after: float | None = None
            for _ in range(len(self.rotator.keys)):
                client = self._clients[self.rotator.key]
                try:
                    response = client.chat.completions.create(
                        model=self.model,
                        max_tokens=max_tokens,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                    )
                    text = response.choices[0].message.content or ""
                    if not text.strip():
                        raise LLMError(f"{self.name} returned no text")
                    return text
                except LLMError:
                    raise
                except Exception as exc:
                    if not _is_rate_limit(exc):
                        raise LLMError(f"{self.name} request failed: {exc}") from exc
                    last_error = exc
                    retry_after = _retry_after_seconds(exc) or retry_after
                    logger.warning("Groq key %d rate limited, rotating", self.rotator.current + 1)
                    self.rotator.rotate()
            if round_number < self.max_rounds - 1:
                delay = retry_after or self.base_delay * (2**round_number)
                logger.warning("All Groq keys rate limited, waiting %.1fs", delay)
                self._sleep(delay)
        raise LLMError(f"{self.name}: all keys rate limited after {self.max_rounds} rounds") from (
            last_error
        )


# ---------------------------------------------------------------------------
# Fallback chain and test double
# ---------------------------------------------------------------------------


class FallbackLLM:
    """Try each client in order until one succeeds."""

    def __init__(self, clients: Sequence[LLMClient]) -> None:
        if not clients:
            raise ValueError("at least one LLM client is required")
        self.clients = list(clients)
        self.name = " -> ".join(c.name for c in self.clients)
        self.last_used: str | None = None

    def complete(self, system: str, prompt: str, max_tokens: int = 4000) -> str:
        errors: list[str] = []
        for client in self.clients:
            try:
                text = client.complete(system, prompt, max_tokens)
            except LLMError as exc:
                logger.warning("%s failed, trying next provider: %s", client.name, exc)
                errors.append(str(exc))
                continue
            self.last_used = client.name
            return text
        raise LLMError("All LLM providers failed: " + " | ".join(errors))


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


def build_llm(settings: Any) -> FallbackLLM:
    """Build the provider chain from settings, skipping providers with no credentials."""
    clients: list[LLMClient] = []
    for provider in settings.provider_order:
        if provider == "bedrock":
            clients.append(
                BedrockClaudeClient(
                    model_id=settings.bedrock_model_id,
                    region=settings.aws_region,
                    aws_profile=settings.aws_profile,
                )
            )
        elif provider == "groq" and settings.groq_key_list:
            clients.append(GroqClient(api_keys=settings.groq_key_list, model=settings.groq_model))
    if not clients:
        raise LLMError("No LLM provider is configured. See .env.example.")
    return FallbackLLM(clients)
