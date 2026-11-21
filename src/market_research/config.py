"""Application settings, loaded from environment variables or a local .env file."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
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
    groq_model: str = "llama-3.3-70b-versatile"

    tavily_api_key: str | None = None

    # Read each result page and keep its most relevant passage (see scraper.py).
    scrape_pages: bool = True

    max_search_results: int = Field(default=5, ge=1, le=10)
    max_revisions: int = Field(default=1, ge=0, le=1)
    log_level: str = "INFO"

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


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
