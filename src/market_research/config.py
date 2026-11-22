"""Application settings, loaded from environment variables or a local .env file."""

import logging
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SUPPORTED_PROVIDERS = ("bedrock", "groq")


class Settings(BaseSettings):
    """Runtime configuration. Every value can be overridden by an environment variable."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Providers offered in the app's model picker, comma separated; the first is the default.
    llm_providers: str = "bedrock,groq"

    # Amazon Bedrock (Claude). Credentials come from the standard AWS chain.
    aws_region: str = "us-east-1"
    aws_profile: str | None = None
    bedrock_model_id: str = "us.anthropic.claude-opus-4-6-v1"
    # "invoke" (InvokeModel, Claude Opus 4.6 and earlier, and newer) or "mantle" (4.7+).
    bedrock_api: Literal["invoke", "mantle"] = "invoke"

    # Groq: one or more keys, comma separated, rotated on rate limits.
    groq_api_keys: str | None = None
    groq_model: str = "openai/gpt-oss-120b"

    tavily_api_key: str | None = None

    # Read each result page and keep its most relevant passage (see scraper.py).
    scrape_pages: bool = True
    # Also read PDF reports found in search results (first 20 pages, up to 10 MB).
    read_pdfs: bool = False

    # Low but not zero: runs stay consistent while wording can still vary slightly.
    llm_temperature: float = Field(default=0.2, ge=0.0, le=1.0)

    max_search_results: int = Field(default=5, ge=1, le=10)
    max_revisions: int = Field(default=1, ge=0, le=1)
    log_level: str = "INFO"

    @field_validator("groq_api_keys", "tavily_api_key", "aws_profile", mode="before")
    @classmethod
    def blank_is_unset(cls, value: object) -> object:
        """'TAVILY_API_KEY=' or a value of only spaces means the key is not set."""
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

    @property
    def provider_order(self) -> list[str]:
        names = [p.strip().lower() for p in self.llm_providers.split(",") if p.strip()]
        unknown = [n for n in names if n not in SUPPORTED_PROVIDERS]
        if unknown:
            raise ValueError(f"Unknown LLM provider(s): {', '.join(unknown)}")
        return names

    @property
    def groq_key_list(self) -> list[str]:
        if not self.groq_api_keys:
            return []
        return [k.strip() for k in self.groq_api_keys.split(",") if k.strip()]

    @property
    def web_search_enabled(self) -> bool:
        """True when a Tavily key is configured; otherwise sample data is used."""
        return bool(self.tavily_api_key)


def configure_logging(level: str) -> None:
    """Apply LOG_LEVEL to the app's own loggers; an unknown level falls back to INFO.

    Records go to the root handlers. If nothing has configured logging yet, a
    plain stderr handler is added once, so repeated calls (Streamlit reruns) are safe.
    """
    resolved = logging.getLevelName(level.strip().upper())
    logging.getLogger("market_research").setLevel(
        resolved if isinstance(resolved, int) else logging.INFO
    )
    logging.basicConfig(format="%(levelname)s %(name)s: %(message)s")
