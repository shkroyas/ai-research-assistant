"""Researcher: plans focused searches and turns results into numbered findings."""

import logging

from pydantic import BaseModel, Field

from market_research.evidence import (
    clean_evidence,
    ensure_focus,
    fallback_focus,
    mentions_focus,
    rank_results,
)
from market_research.llm import LLMClient, LLMError, complete_json
from market_research.models import Finding, ResearchState
from market_research.prompts import RESEARCHER_SYSTEM
from market_research.scraper import PageScraper, ScrapeResult
from market_research.search import SearchProvider, SearchResult

logger = logging.getLogger(__name__)

MAX_FINDINGS = 10
MAX_CLAIM_CHARS = 600


class SearchPlan(BaseModel):
    focus: list[str] = Field(default_factory=list, max_length=4)
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

    def plan(self, query: str) -> SearchPlan:
        """Ask the model for the focus and the searches; fall back to the raw query."""
        try:
            plan = complete_json(
                self.llm,
                RESEARCHER_SYSTEM,
                f"User request: {query}\n\nIdentify the focus and plan 2 to 4 web searches.",
                SearchPlan,
                max_tokens=1000,
            )
        except LLMError as exc:
            logger.warning("Query planning failed, searching the raw query: %s", exc)
            plan = SearchPlan(queries=[query])
        focus = [f.strip() for f in plan.focus if f.strip()] or fallback_focus(query)
        queries = [q.strip() for q in plan.queries if q.strip()] or [query]
        return SearchPlan(focus=focus, queries=ensure_focus(queries, focus))

    def run(self, state: ResearchState) -> ResearchState:
        plan = self.plan(state.query)
        state.focus = plan.focus
        state.log(
            self.name,
            "planned searches",
            focus=plan.focus,
            queries=plan.queries,
            source=self.search.name,
        )

        results: list[SearchResult] = []
        seen: set[str] = set()
        dropped = 0
        for search_query in plan.queries:
            for result in self.search.search(search_query, max_results=self.max_results):
                key = result.url or result.title
                if key in seen:
                    continue
                seen.add(key)
                content = clean_evidence(result.content)
                if not content:
                    dropped += 1  # nothing usable left, e.g. only masked figures
                    continue
                results.append(result.model_copy(update={"content": content}))

        ranked = rank_results(results, plan.focus, limit=MAX_FINDINGS)
        pages = self._scrape(state, [r for r, _ in ranked], plan.focus)

        state.findings = [
            _to_finding(i, result, on_focus, pages.get(result.url or ""), plan.focus)
            for i, (result, on_focus) in enumerate(ranked, start=1)
        ]
        state.log(
            self.name,
            "collected findings",
            count=len(state.findings),
            on_focus=sum(f.on_focus for f in state.findings),
            scraped=sum(f.evidence == "scraped page" for f in state.findings),
            dropped_unusable=dropped,
            sample_data=state.uses_sample_data,
        )
        return state

    def _scrape(
        self, state: ResearchState, results: list[SearchResult], focus: list[str]
    ) -> dict[str, ScrapeResult]:
        """Read the result pages; sample data and URL-less results are never scraped."""
        urls = [r.url for r in results if r.url and not r.is_sample_data]
        if self.scraper is None or not urls:
            return {}
        pages = self.scraper.scrape_many(urls, state.query, focus=focus)
        state.log(
            self.name,
            "read source pages",
            used=sum(p.ok for p in pages.values()),
            skipped={url: p.reason for url, p in pages.items() if not p.ok},
        )
        return pages


def _to_finding(
    index: int,
    result: SearchResult,
    on_focus: bool,
    page: ScrapeResult | None,
    focus: list[str],
) -> Finding:
    if result.is_sample_data:
        claim, evidence = result.content, "sample data"
    elif page is not None and page.ok and page.passage:
        claim, evidence = page.passage, "scraped page"
        on_focus = on_focus or mentions_focus([page.passage], focus)
    else:
        claim, evidence = result.content, "search snippet"
    return Finding(
        id=f"F{index}",
        claim=_shorten(claim),
        source_title=result.title,
        source_url=result.url,
        is_sample_data=result.is_sample_data,
        evidence=evidence,
        on_focus=on_focus,
    )


def _shorten(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= MAX_CLAIM_CHARS else text[: MAX_CLAIM_CHARS - 3].rstrip() + "..."
