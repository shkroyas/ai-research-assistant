"""Critic: checks the draft against the evidence and approves or asks for a revision."""

from market_research.agents.analyst import format_findings
from market_research.grounding import check_grounding
from market_research.llm import LLMClient, complete_json
from market_research.models import Critique, ResearchState
from market_research.prompts import CRITIC_SYSTEM


class Critic:
    name = "Critic"

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def run(self, state: ResearchState) -> ResearchState:
        if state.draft is None:
            raise ValueError("Critic needs a draft brief")

        problems = check_grounding(state.draft, state.findings)
        prompt = (
            f"User request: {state.query}\n\nFindings:\n{format_findings(state.findings)}"
            f"\n\nDraft brief:\n{state.draft.model_dump_json(indent=2)}"
        )
        if problems:
            prompt += "\n\nAutomated citation check found:\n- " + "\n- ".join(problems)

        critique = complete_json(self.llm, CRITIC_SYSTEM, prompt, Critique, max_tokens=1500)

        # Citation problems found in code always block approval, whatever the model says.
        if problems:
            critique.approved = False
            critique.issues = [*problems, *critique.issues]
            critique.revision_request = critique.revision_request or (
                "Fix the citation problems: cite only existing finding ids and support "
                "every observation and competitor with findings."
            )

        state.critique = critique
        state.log(
            self.name,
            "approved brief" if critique.approved else "requested revision",
            issues=critique.issues,
        )
        return state
