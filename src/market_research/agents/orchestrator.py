"""Orchestrator: receives the query and runs Researcher -> Analyst -> Critic."""

from collections.abc import Callable

from market_research.agents.analyst import Analyst
from market_research.agents.critic import Critic
from market_research.agents.researcher import Researcher
from market_research.models import ResearchState

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

    def run(self, query: str, on_step: StepCallback | None = None) -> ResearchState:
        def notify(agent: str, state: ResearchState) -> None:
            if on_step is not None:
                on_step(agent, state)

        state = ResearchState(query=query)
        state.log(self.name, "received query", query=state.query)
        notify(self.name, state)

        state = self.researcher.run(state)
        notify(self.researcher.name, state)

        state = self.analyst.run(state)
        notify(self.analyst.name, state)

        state = self.critic.run(state)
        notify(self.critic.name, state)

        while (
            state.critique is not None
            and not state.critique.approved
            and state.revisions_used < self.max_revisions
        ):
            state.revisions_used += 1
            state = self.analyst.run(state)
            notify(self.analyst.name, state)
            state = self.critic.run(state)
            notify(self.critic.name, state)

        approved = state.critique is not None and state.critique.approved
        state.log(
            self.name,
            "finished",
            approved=approved,
            revisions_used=state.revisions_used,
        )
        notify(self.name, state)
        return state
