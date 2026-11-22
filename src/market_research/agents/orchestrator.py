"""Orchestrator: receives the query and runs Researcher -> Analyst -> Critic."""

import time
from collections.abc import Callable

from market_research.agents.analyst import Analyst
from market_research.agents.critic import Critic
from market_research.agents.researcher import Researcher
from market_research.models import ResearchState
from market_research.quality import assess

StepCallback = Callable[[str, ResearchState], None]


class Orchestrator:
    name = "Orchestrator"

    def __init__(
        self,
        researcher: Researcher,
        analyst: Analyst,
        critic: Critic,
        max_revisions: int = 1,
    ) -> None:
        self.researcher = researcher
        self.analyst = analyst
        self.critic = critic
        self.max_revisions = max_revisions

    def close(self) -> None:
        """Release network resources held by the agents (the Researcher's page scraper)."""
        self.researcher.close()

    def run(self, query: str, on_step: StepCallback | None = None) -> ResearchState:
        def notify(agent: str, state: ResearchState) -> None:
            if on_step is not None:
                on_step(agent, state)

        def step(agent, state: ResearchState) -> ResearchState:
            """Run one agent, record how long it took on its last trace entry, then notify."""
            started = time.perf_counter()
            state = agent.run(state)
            state.trace[-1].duration_ms = round((time.perf_counter() - started) * 1000)
            notify(agent.name, state)
            return state

        run_started = time.perf_counter()
        state = ResearchState(query=query)
        state.log(self.name, "received query", query=state.query)
        notify(self.name, state)

        state = step(self.researcher, state)
        if not state.intake.proceed:
            # Unclear or declined: ask or explain instead of writing a brief from guesses.
            state.duration_ms = round((time.perf_counter() - run_started) * 1000)
            state.log(self.name, "stopped before research", status=state.intake.status)
            state.trace[-1].duration_ms = state.duration_ms
            notify(self.name, state)
            return state

        state = step(self.analyst, state)
        state = step(self.critic, state)

        while (
            state.critique is not None
            and not state.critique.approved
            and state.revisions_used < self.max_revisions
        ):
            state.revisions_used += 1
            state = step(self.analyst, state)
            state = step(self.critic, state)

        approved = state.critique is not None and state.critique.approved
        state.quality = assess(state)
        state.duration_ms = round((time.perf_counter() - run_started) * 1000)
        state.log(
            self.name,
            "finished",
            approved=approved,
            revisions_used=state.revisions_used,
            citation_coverage=state.quality.citation_coverage,
        )
        state.trace[-1].duration_ms = state.duration_ms
        notify(self.name, state)
        return state
