"""Streamlit front end for the multi-agent market research assistant."""

import logging
from dataclasses import dataclass
from datetime import datetime

import streamlit as st

from market_research import pipeline
from market_research.config import Settings
from market_research.intake import MAX_QUERY_CHARS
from market_research.llm import PROVIDER_LABELS, LLMError, available_providers
from market_research.models import ResearchState
from ui import components
from ui.text import short

logger = logging.getLogger(__name__)

st.set_page_config(page_title="AI Research Assistant", page_icon="🔎", layout="wide")

EXAMPLES = [
    "Analyze the food delivery market in Nepal",
    "Research Tesla and its main competitors",
    "Compare eSewa and Khalti digital wallets in Nepal",
    "AI adoption in banking",
]
MAX_HISTORY = 10
EXPECTED_STEPS = 5  # Orchestrator, Researcher, Analyst, Critic, Orchestrator (no revision)


@dataclass
class Run:
    state: ResearchState
    model_label: str
    finished_at: datetime


def init_state() -> None:
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("selected", 0)
    st.session_state.setdefault("query_input", "")
    st.session_state.setdefault("autorun", False)
    # Widget-bound keys can only change before their widget is drawn, so a new run
    # asks for the selection to move to it on the next rerun.
    if st.session_state.pop("select_latest", False):
        st.session_state["selected"] = 0


def clear_history() -> None:
    st.session_state["history"] = []
    st.session_state["selected"] = 0


def pick_example(query: str) -> None:
    st.session_state["query_input"] = query
    st.session_state["autorun"] = True


def model_caption(settings: Settings, provider: str) -> str:
    if provider == "bedrock":
        return f"`{settings.bedrock_model_id}` · {settings.aws_region}"
    keys = len(settings.groq_key_list)
    return f"`{settings.groq_model}` · {keys} key{'s' if keys != 1 else ''} in rotation"


def sidebar(settings: Settings) -> tuple[str | None, Settings]:
    """Model and research controls, plus this session's run history."""
    with st.sidebar:
        st.subheader("Model")
        providers = available_providers(settings)
        if not providers:
            st.error("No model is configured. Add keys to `.env` (see the README).")
            return None, settings
        provider = st.radio(
            "Model",
            providers,
            format_func=lambda p: PROVIDER_LABELS[p],
            label_visibility="collapsed",
        )
        st.caption(model_caption(settings, provider))

        st.subheader("Research")
        if settings.web_search_enabled:
            st.caption("Web search: Tavily, live")
        else:
            st.caption("Web search: off, using labelled sample data")
        scrape = st.toggle(
            "Read full source pages",
            value=settings.scrape_pages,
            help="Fetch each result page (respecting robots.txt) and keep its most relevant "
            "passage instead of the short search snippet.",
            disabled=not settings.web_search_enabled,
        )
        depth = st.slider(
            "Results per search", 1, 10, settings.max_search_results, help="Up to 4 searches run"
        )

        history: list[Run] = st.session_state["history"]
        if history:
            st.subheader("This session")
            st.radio(
                "Earlier runs",
                range(len(history)),
                key="selected",
                format_func=lambda i: (
                    f"{short(history[i].state.query, 34)} · {history[i].finished_at:%H:%M}"
                ),
                label_visibility="collapsed",
            )
            st.button("Clear history", on_click=clear_history, width="stretch")

    tuned = settings.model_copy(update={"scrape_pages": scrape, "max_search_results": depth})
    return provider, tuned


def run_research(query: str, settings: Settings, provider: str) -> Run | None:
    try:
        orchestrator = pipeline.build_orchestrator(settings, provider)
        with st.status("Running agents...", expanded=True) as status:
            progress = st.progress(0.0)

            def on_step(agent: str, state: ResearchState) -> None:
                step = state.trace[-1]
                st.write(f"**{step.agent}**: {step.action}")
                progress.progress(min(len(_agent_steps(state)) / EXPECTED_STEPS, 1.0))

            state = orchestrator.run(query, on_step=on_step)
            progress.progress(1.0)
            label = "Research complete" if state.intake.proceed else "Stopped before research"
            status.update(label=label, state="complete", expanded=False)
    except LLMError as exc:
        st.error(f"The model could not complete the request: {exc}")
        return None
    except Exception:  # never show a traceback: explain, log, and keep the page usable
        logger.exception("Research run failed")
        st.error(
            "Something went wrong while researching this request. Please try again, or try "
            "another model. The details are in the app log."
        )
        return None
    return Run(state=state, model_label=PROVIDER_LABELS[provider], finished_at=datetime.now())


def _agent_steps(state: ResearchState) -> list:
    """One entry per agent handoff (an agent may log several trace lines in one step)."""
    return [t for t in state.trace if t.duration_ms is not None or t.action == "received query"]


def main() -> None:
    init_state()
    st.title("AI Research Assistant")
    st.caption(
        "Four agents (Orchestrator, Researcher, Analyst, Critic) turn a company or industry "
        "into a short, sourced research brief."
    )

    try:
        settings = Settings()
        provider, settings = sidebar(settings)
    except ValueError as exc:
        st.error(f"Configuration problem: {exc}")
        return
    if provider is None:
        return

    with st.form("query", border=False):
        col_input, col_button = st.columns([5, 1], vertical_alignment="bottom")
        query = col_input.text_input(
            "Market, company or topic",
            key="query_input",
            placeholder=EXAMPLES[0],
            max_chars=MAX_QUERY_CHARS,
        )
        submitted = col_button.form_submit_button("Run research", type="primary", width="stretch")

    if st.session_state["autorun"]:
        st.session_state["autorun"] = False
        submitted = True

    if submitted:
        if not query.strip():
            st.warning("Please enter a company or industry.")
        else:
            run = run_research(query, settings, provider)
            if run is not None and not run.state.intake.proceed:
                # Ask for clarity or explain the refusal; nothing is added to the history.
                components.clarify(run.state, pick_example)
                return
            if run is not None:
                history: list[Run] = st.session_state["history"]
                history.insert(0, run)
                del history[MAX_HISTORY:]
                st.session_state["select_latest"] = True
                st.rerun()

    history = st.session_state["history"]
    if history:
        current = history[min(st.session_state["selected"], len(history) - 1)]
        components.results(current.state, current.model_label)
    else:
        components.hero(EXAMPLES, pick_example)


main()
