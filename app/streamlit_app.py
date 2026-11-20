"""Streamlit front end for the multi-agent market research assistant."""

import json

import streamlit as st

from market_research import pipeline
from market_research.config import Settings
from market_research.llm import PROVIDER_LABELS, LLMError, available_providers
from market_research.models import ResearchState
from market_research.render import brief_to_markdown

st.set_page_config(page_title="AI Research Assistant", page_icon="🔎", layout="centered")

EXAMPLE_QUERY = "Analyze the food delivery market in Nepal"


def model_caption(settings: Settings, provider: str) -> str:
    if provider == "bedrock":
        return f"`{settings.bedrock_model_id}` · {settings.aws_region}"
    keys = len(settings.groq_key_list)
    return f"`{settings.groq_model}` · {keys} key{'s' if keys != 1 else ''} in rotation"


def sidebar(settings: Settings) -> str | None:
    with st.sidebar:
        st.subheader("Model")
        providers = available_providers(settings)
        if not providers:
            st.error("No model is configured. Add keys to `.env` (see the README).")
            return None
        provider = st.radio(
            "Model",
            providers,
            format_func=lambda p: PROVIDER_LABELS[p],
            label_visibility="collapsed",
        )
        st.caption(model_caption(settings, provider))

        st.subheader("Web search")
        if settings.web_search_enabled:
            st.caption("Tavily live search")
        else:
            st.caption("Off. Using labelled sample data.")
        return provider


def show_summary_bar(state: ResearchState, model_label: str) -> None:
    critique = state.critique
    verdict = "Approved" if critique and critique.approved else "Not approved"
    col_model, col_findings, col_critic = st.columns(3)
    col_model.metric("Model", model_label)
    col_findings.metric("Findings", len(state.findings))
    col_critic.metric("Critic", verdict, f"{state.revisions_used} revision(s)", delta_color="off")


def show_brief(state: ResearchState) -> None:
    brief = state.draft
    if brief is None:
        st.error("No brief was produced.")
        return

    if state.uses_sample_data:
        st.warning("These findings come from the built-in sample dataset, not live web search.")

    with st.container(border=True):
        st.markdown(f"### {state.query}")
        st.markdown("**Summary**")
        st.write(brief.summary)

        st.markdown("**Competitors**")
        if brief.competitors:
            for c in brief.competitors:
                refs = f" `{', '.join(c.finding_ids)}`" if c.finding_ids else ""
                st.markdown(f"- **{c.name}**: {c.note}{refs}")
        else:
            st.caption("None identified from the available evidence.")

        st.markdown("**Key observations**")
        for observation in brief.observations:
            st.markdown(f"- {observation}")

        st.markdown("**Sources**")
        for source in brief.sources or ["No sources were cited."]:
            st.markdown(f"- {source}")

        st.markdown("**Missing information**")
        for item in brief.missing_information or ["None noted."]:
            st.markdown(f"- {item}")

    critique = state.critique
    if critique and not critique.approved and critique.issues:
        with st.expander("Critic notes"):
            for issue in critique.issues:
                st.markdown(f"- {issue}")

    col_md, col_json = st.columns(2)
    col_md.download_button(
        "Download brief (.md)",
        brief_to_markdown(state),
        file_name="research-brief.md",
        use_container_width=True,
    )
    col_json.download_button(
        "Download full run (.json)",
        json.dumps(state.model_dump(mode="json"), indent=2),
        file_name="research-run.json",
        use_container_width=True,
    )


def show_trace(state: ResearchState) -> None:
    with st.expander("Agent trace"):
        for step in state.trace:
            st.markdown(f"**{step.agent}** · {step.action}")
            if step.detail:
                st.json(step.detail, expanded=False)
        st.markdown("**Findings passed to the Analyst**")
        for f in state.findings:
            label = " · sample data" if f.is_sample_data else ""
            st.markdown(f"- `{f.id}` {f.claim} _({f.source_title}{label})_")


def main() -> None:
    st.title("AI Research Assistant")
    st.caption(
        "Four agents (Orchestrator, Researcher, Analyst, Critic) turn a company or "
        "industry into a short, sourced research brief."
    )

    try:
        settings = Settings()
        provider = sidebar(settings)
    except ValueError as exc:
        st.error(f"Configuration problem: {exc}")
        return
    if provider is None:
        return

    with st.form("query", border=False):
        query = st.text_input("Company or industry", placeholder=EXAMPLE_QUERY)
        submitted = st.form_submit_button("Run research", type="primary")

    if submitted:
        if not query.strip():
            st.warning("Please enter a company or industry.")
            return
        try:
            orchestrator = pipeline.build_orchestrator(settings, provider)
            with st.status("Running agents...", expanded=True) as status:

                def on_step(agent: str, state: ResearchState) -> None:
                    st.write(f"{state.trace[-1].agent}: {state.trace[-1].action}")

                state = orchestrator.run(query, on_step=on_step)
                status.update(label="Research complete", state="complete", expanded=False)
            st.session_state["result"] = (state, PROVIDER_LABELS[provider])
        except LLMError as exc:
            st.error(f"The model could not complete the request: {exc}")
            return

    result = st.session_state.get("result")
    if result is not None:
        state, model_label = result
        show_summary_bar(state, model_label)
        show_brief(state)
        show_trace(state)


main()
