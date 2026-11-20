"""Researcher: plans search queries and turns search results into numbered findings."""

import logging

from pydantic import BaseModel, Field

from market_research.llm import LLMClient, LLMError, complete_json
from market_research.models import Finding, ResearchState
from market_research.prompts import RESEARCHER_SYSTEM
from market_research.search import SearchProvider, SearchResult

logger = logging.getLogger(__name__)

MAX_FINDINGS = 10
MAX_CLAIM_CHARS = 600


class SearchPlan(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=4)


class Researcher:
    name = "Researcher"

    def __init__(self, llm: LLMClient, search: SearchProvider, max_results: int = 5) -> None:
        self.llm = llm
        self.search = search
        self.max_results = max_results

    def plan_queries(self, query: str) -> list[str]:
        try:
            plan = complete_json(
                self.llm,
                RESEARCHER_SYSTEM,
                f"User request: {query}\n\nPlan 2 to 4 web search queries.",
                SearchPlan,
                max_tokens=1000,
            )
            return [q.strip() for q in plan.queries if q.strip()] or [query]
        except LLMError as exc:
            logger.warning("Query planning failed, searching the raw query: %s", exc)
            return [query]

    def run(self, state: ResearchState) -> ResearchState:
        queries = self.plan_queries(state.query)
        state.log(self.name, "planned searches", queries=queries, source=self.search.name)

        results: list[SearchResult] = []
        seen: set[str] = set()
        for search_query in queries:
            for result in self.search.search(search_query, max_results=self.max_results):
                key = result.url or result.title
                if key not in seen:
                    seen.add(key)
                    results.append(result)

        state.findings = [
            Finding(
                id=f"F{i}",
                claim=_shorten(result.content),
                source_title=result.title,
                source_url=result.url,
                is_sample_data=result.is_sample_data,
            )
            for i, result in enumerate(results[:MAX_FINDINGS], start=1)
        ]
        state.log(
            self.name,
            "collected findings",
            count=len(state.findings),
            sample_data=state.uses_sample_data,
        )
        return state


def _shorten(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= MAX_CLAIM_CHARS else text[: MAX_CLAIM_CHARS - 3].rstrip() + "..."
