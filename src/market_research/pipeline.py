"""Wire settings, model clients and search into a ready-to-run Orchestrator."""

from market_research.agents import Analyst, Critic, Orchestrator, Researcher
from market_research.config import Settings
from market_research.llm import build_llm
from market_research.search import build_search


def build_orchestrator(settings: Settings, provider: str | None = None) -> Orchestrator:
    llm = build_llm(settings, provider)
    search = build_search(settings.tavily_api_key)
    return Orchestrator(
        researcher=Researcher(llm, search, max_results=settings.max_search_results),
        analyst=Analyst(llm),
        critic=Critic(llm),
        max_revisions=settings.max_revisions,
    )
