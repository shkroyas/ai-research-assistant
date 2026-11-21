"""Researcher: plans search queries and turns search results into numbered findings."""

import logging

from pydantic import BaseModel, Field

from market_research.llm import LLMClient, LLMError, complete_json
from market_research.models import Finding, ResearchState
from market_research.prompts import RESEARCHER_SYSTEM
from market_research.scraper import PageScraper, ScrapeResult
from market_research.search import SearchProvider, SearchResult

logger = logging.getLogger(__name__)

MAX_FINDINGS = 10
MAX_CLAIM_CHARS = 600


class SearchPlan(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=4)


class Researcher:
    name = "Researcher"

    def __init__(
        self,
        llm: LLMClient,
        search: SearchProvider,
        max_results: int = 5,
        scraper: PageScraper | None = None,
    ) -> None:
        self.llm = llm
        self.search = search
        self.max_results = max_results
        self.scraper = scraper

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

        results = results[:MAX_FINDINGS]
        pages = self._scrape(state, results)

        state.findings = [
            _to_finding(i, result, pages.get(result.url or ""))
            for i, result in enumerate(results, start=1)
        ]
        state.log(
            self.name,
            "collected findings",
            count=len(state.findings),
            scraped=sum(f.evidence == "scraped page" for f in state.findings),
            sample_data=state.uses_sample_data,
        )
        return state

    def _scrape(self, state: ResearchState, results: list[SearchResult]) -> dict[str, ScrapeResult]:
        """Read the result pages; sample data and URL-less results are never scraped."""
        urls = [r.url for r in results if r.url and not r.is_sample_data]
        if self.scraper is None or not urls:
            return {}
        pages = self.scraper.scrape_many(urls, state.query)
        state.log(
            self.name,
            "read source pages",
            used=sum(p.ok for p in pages.values()),
            skipped={url: p.reason for url, p in pages.items() if not p.ok},
        )
        return pages


def _to_finding(index: int, result: SearchResult, page: ScrapeResult | None) -> Finding:
    if result.is_sample_data:
        claim, evidence = result.content, "sample data"
    elif page is not None and page.ok and page.passage:
        claim, evidence = page.passage, "scraped page"
    else:
        claim, evidence = result.content, "search snippet"
    return Finding(
        id=f"F{index}",
        claim=_shorten(claim),
        source_title=result.title,
        source_url=result.url,
        is_sample_data=result.is_sample_data,
        evidence=evidence,
    )


def _shorten(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= MAX_CLAIM_CHARS else text[: MAX_CLAIM_CHARS - 3].rstrip() + "..."
