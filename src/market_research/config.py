"""Application settings, loaded from environment variables or a local .env file."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Every value can be overridden by an environment variable."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_api_key: str | None = None
    llm_model: str | None = None
    tavily_api_key: str | None = None

    max_search_results: int = Field(default=5, ge=1, le=10)
    max_revisions: int = Field(default=1, ge=0, le=1)
    log_level: str = "INFO"

    @property
    def web_search_enabled(self) -> bool:
        """True when a Tavily key is configured; otherwise sample data is used."""
        return bool(self.tavily_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
