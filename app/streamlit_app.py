"""Streamlit front end for the multi-agent market research assistant."""

import json

import streamlit as st

from market_research import pipeline
from market_research.config import Settings
from market_research.llm import LLMError
from market_research.models import ResearchState
from market_research.render import brief_to_markdown

st.set_page_config(page_title="AI Research Assistant", page_icon="🔎", layout="wide")


def sidebar(settings: Settings) -> None:
    with st.sidebar:
        st.header("Configuration")
        st.markdown(f"**LLM providers (in order):** {', '.join(settings.provider_order)}")
        if settings.web_search_enabled:
            st.success("Web search: Tavily")
        else:
            st.warning("Web search: off. Using labelled sample data.")
        st.caption(f"Critic may request up to {settings.max_revisions} revision(s).")
        st.divider()
        st.caption("Settings come from your `.env` file. See the README.")


def show_brief(state: ResearchState) -> None:
    brief = state.draft
    if brief is None:
        st.error("No brief was produced.")
        return

    if state.uses_sample_data:
        st.warning(
            "Sample data: these findings come from the built-in sample dataset, "
            "not live web search."
        )

    critique = state.critique
    if critique and critique.approved:
        st.success(f"Approved by the Critic after {state.revisions_used} revision(s).")
    else:
        st.info("The Critic did not fully approve this brief. Its notes are below.")

    st.subheader("Summary")
    st.write(brief.summary)

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Competitors")
        if brief.competitors:
            for c in brief.competitors:
                refs = f" `{', '.join(c.finding_ids)}`" if c.finding_ids else ""
                st.markdown(f"**{c.name}**: {c.note}{refs}")
        else:
            st.write("None identified from the available evidence.")
    with col_right:
        st.subheader("Missing information")
        for item in brief.missing_information or ["None noted."]:
            st.markdown(f"- {item}")

    st.subheader("Key observations")
    for observation in brief.observations:
        st.markdown(f"- {observation}")

    st.subheader("Sources")
    for source in brief.sources or ["No sources were cited."]:
        st.markdown(f"- {source}")

    if critique and not critique.approved and critique.issues:
        with st.expander("Critic notes"):
            for issue in critique.issues:
                st.markdown(f"- {issue}")

    markdown = brief_to_markdown(state)
    col_md, col_json = st.columns(2)
    col_md.download_button("Download brief (Markdown)", markdown, file_name="research-brief.md")
    col_json.download_button(
        "Download full run (JSON)",
        json.dumps(state.model_dump(mode="json"), indent=2),
        file_name="research-run.json",
    )


def show_trace(state: ResearchState) -> None:
    with st.expander("Agent trace: every handoff, in order"):
        for step in state.trace:
            st.markdown(f"**{step.agent}**: {step.action}")
            if step.detail:
                st.json(step.detail, expanded=False)
        with st.container():
            st.markdown("**Findings passed to the Analyst**")
            for f in state.findings:
                label = " (sample data)" if f.is_sample_data else ""
                st.markdown(f"- `{f.id}` {f.claim} _({f.source_title}{label})_")


def main() -> None:
    st.title("🔎 AI Research Assistant")
    st.caption(
        "Enter a company or industry. Four agents (Orchestrator, Researcher, "
        "Analyst, Critic) produce a short, sourced research brief."
    )

    try:
        settings = Settings()
        sidebar(settings)
    except ValueError as exc:
        st.error(f"Configuration problem: {exc}")
        return

    with st.form("query"):
        query = st.text_input(
            "Company or industry",
            placeholder="Analyze the food delivery market in Nepal",
        )
        submitted = st.form_submit_button("Run research", type="primary")

    if submitted:
        if not query.strip():
            st.warning("Please enter a company or industry.")
            return
        try:
            orchestrator = pipeline.build_orchestrator(settings)
            with st.status("Running agents...", expanded=True) as status:

                def on_step(agent: str, state: ResearchState) -> None:
                    st.write(f"✓ {state.trace[-1].agent}: {state.trace[-1].action}")

                state = orchestrator.run(query, on_step=on_step)
                status.update(label="Research complete", state="complete", expanded=False)
            st.session_state["result"] = state
        except LLMError as exc:
            st.error(f"The language model could not complete the request: {exc}")
            return

    result = st.session_state.get("result")
    if result is not None:
        show_brief(result)
        show_trace(result)


main()
