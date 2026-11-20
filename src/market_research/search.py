"""Web search for the Researcher, with an honest offline fallback.

TavilySearch calls the Tavily API. SampleDataSearch reads hand-written JSON
files from data/sample/ and marks every result as sample data, so the UI and
the brief can label it clearly.
"""

import json
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

DEFAULT_SAMPLE_DIR = Path(__file__).resolve().parents[2] / "data" / "sample"


class SearchResult(BaseModel):
    title: str
    url: str | None = None
    content: str
    is_sample_data: bool = False


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]: ...


class TavilySearch:
    """Live web search through the Tavily API."""

    name = "Tavily web search"

    def __init__(self, api_key: str, client: object | None = None) -> None:
        if client is None:
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)
        self._client = client

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        response = self._client.search(query=query, max_results=max_results)  # type: ignore[attr-defined]
        return [
            SearchResult(
                title=item.get("title", "Untitled"), url=item.get("url"), content=item["content"]
            )
            for item in response.get("results", [])
            if item.get("content")
        ]


class SampleDataSearch:
    """Offline search over clearly labelled sample data."""

    name = "Sample data (offline)"

    def __init__(self, sample_dir: Path = DEFAULT_SAMPLE_DIR) -> None:
        self._datasets = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(sample_dir.glob("*.json"))
        ]

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        lowered = query.lower()
        best = max(
            self._datasets,
            key=lambda d: sum(keyword in lowered for keyword in d.get("keywords", [])),
            default=None,
        )
        if best is None or not any(k in lowered for k in best.get("keywords", [])):
            return []
        return [
            SearchResult(
                title=item["title"],
                url=item.get("url"),
                content=item["content"],
                is_sample_data=True,
            )
            for item in best["results"][:max_results]
        ]


def build_search(tavily_api_key: str | None) -> SearchProvider:
    """Use Tavily when a key is configured, otherwise labelled sample data."""
    if tavily_api_key:
        return TavilySearch(api_key=tavily_api_key)
    return SampleDataSearch()
