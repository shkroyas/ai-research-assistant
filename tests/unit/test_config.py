import pytest
from pydantic import ValidationError

from market_research.config import Settings


def test_defaults_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    assert settings.max_revisions == 1
    assert settings.web_search_enabled is False


def test_web_search_enabled_with_key() -> None:
    settings = Settings(_env_file=None, tavily_api_key="tvly-test")
    assert settings.web_search_enabled is True


def test_max_revisions_is_capped_at_one() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, max_revisions=2)
