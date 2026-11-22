"""Page sections. Each function renders one part of the page from a finished run."""

import json

import streamlit as st

from market_research.models import ResearchState
from market_research.quality import brief_citations
from market_research.render import brief_to_markdown
from ui.text import format_ms, link_citations, short

AGENTS = [
    ("Orchestrator", "Receives the query, runs the workflow and enforces the one-revision limit."),
    ("Researcher", "Plans searches, reads the source pages and numbers every finding F1, F2, ..."),
    ("Analyst", "Writes the brief from the findings only, citing each claim."),
    ("Critic", "Checks citations in code and the evidence with the model; may ask for one fix."),
]

WORKFLOW = """
digraph {
  rankdir=LR; bgcolor="transparent";
  node [shape=box, style="rounded,filled", fillcolor="#eef3fd", color="#1f6feb",
        fontname="Helvetica", fontsize=11];
  edge [color="#57606a", fontname="Helvetica", fontsize=9];
  Q [label="Your query", shape=oval, fillcolor="#ffffff"];
  S [label="Web search\\n+ page reading", shape=cylinder, fillcolor="#ffffff"];
  B [label="Sourced brief", shape=note, fillcolor="#ffffff"];
  Q -> Orchestrator -> Researcher -> Analyst -> Critic;
  Researcher -> S [dir=both, style=dashed];
  Critic -> Analyst [label="revise (max 1)", style=dashed];
  Critic -> B [label="approved"];
}
"""


def hero(examples: list[str], on_pick) -> None:
    """Landing view: what the app does, how the agents work, and one-click examples."""
    st.markdown("#### Try an example")
    cols = st.columns(len(examples))
    for col, example in zip(cols, examples, strict=True):
        col.button(
            example,
            key=f"example-{example}",
            on_click=on_pick,
            args=(example,),
            width="stretch",
        )

    st.markdown("#### How it works")
    st.graphviz_chart(WORKFLOW, width="stretch")
    cols = st.columns(len(AGENTS))
    for col, (name, job) in zip(cols, AGENTS, strict=True):
        with col.container(border=True):
            st.markdown(f"**{name}**")
            st.caption(job)
    st.caption(
        "Every claim in the brief cites a numbered finding, and code blocks approval when a "
        "citation is missing or invented. Gaps are listed, not guessed."
    )


def metric_row(state: ResearchState, model_label: str) -> None:
    q = state.quality
    critique = state.critique
    verdict = "Approved" if critique and critique.approved else "Not approved"
    cols = st.columns([1, 1, 1, 1.3, 1.5, 1])
    cols[0].metric("Model", model_label.split(" (")[0], help=model_label)
    cols[1].metric("Findings", len(state.findings))
    cols[2].metric("Sources", len(q.domains) if q else "-", help="Distinct source domains")
    cols[3].metric(
        "Citation coverage",
        f"{q.citation_coverage:.0%}" if q else "-",
        help="Share of findings the brief cites",
    )
    cols[4].metric("Critic", verdict, help=f"{state.revisions_used} revision(s) requested")
    cols[5].metric("Run time", format_ms(state.duration_ms))


def brief_tab(state: ResearchState) -> None:
    brief = state.draft
    if brief is None:
        st.error("No brief was produced.")
        return
    if state.uses_sample_data:
        st.warning("These findings come from the built-in sample dataset, not live web search.")

    findings = state.findings
    with st.container(border=True):
        st.markdown(f"### {state.query}")
        st.markdown("**Summary**")
        st.markdown(link_citations(brief.summary, findings))

        st.markdown("**Competitors**")
        if brief.competitors:
            cols = st.columns(len(brief.competitors))
            for col, c in zip(cols, brief.competitors, strict=True):
                with col.container(border=True):
                    st.markdown(f"**{c.name}**")
                    refs = f" [{', '.join(c.finding_ids)}]" if c.finding_ids else ""
                    st.markdown(link_citations(c.note + refs, findings))
        else:
            st.caption("None identified from the available evidence.")

        st.markdown("**Key observations**")
        for observation in brief.observations:
            st.markdown(f"- {link_citations(observation, findings)}")

        st.markdown("**Sources**")
        for source in brief.sources or ["No sources were cited."]:
            st.markdown(f"- {source}")

        st.markdown("**Missing information**")
        for item in brief.missing_information or ["None noted."]:
            st.markdown(f"- {item}")


def evidence_tab(state: ResearchState) -> None:
    if not state.findings:
        st.info("No findings were collected for this query.")
        return
    cited = brief_citations(state.draft) if state.draft else set()
    rows = [
        {
            "ID": f.id,
            "Cited": f.id in cited,
            "On focus": f.on_focus,
            "Evidence": f.claim,
            "Source": f.source_title,
            "Domain": f.domain or "-",
            "Obtained from": f.evidence,
            "Link": f.source_url,
        }
        for f in state.findings
    ]
    if state.focus:
        st.caption(
            f"Focus: **{', '.join(state.focus)}**. Findings that do not mention it are kept as "
            "background only."
        )
    st.caption(
        "Raw evidence passed to the Analyst. *Scraped page* means the passage was read from the "
        "source page itself; *search snippet* means the page could not be used."
    )
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_config={
            "ID": st.column_config.TextColumn(width="small"),
            "Cited": st.column_config.CheckboxColumn(width="small"),
            "On focus": st.column_config.CheckboxColumn(width="small"),
            "Evidence": st.column_config.TextColumn(width="large"),
            "Source": st.column_config.TextColumn(width="medium"),
            "Link": st.column_config.LinkColumn(display_text="open", width="small"),
        },
    )
    skipped = next(
        (t.detail.get("skipped") for t in state.trace if t.action == "read source pages"), None
    )
    if skipped:
        with st.expander(f"Pages that could not be read ({len(skipped)})"):
            for url, reason in skipped.items():
                st.markdown(f"- `{reason}`: {url}")


def quality_tab(state: ResearchState) -> None:
    q = state.quality
    if q is not None:
        st.markdown("**Evidence quality** (measured in code)")
        st.progress(q.citation_coverage, text=f"Citation coverage: {q.citation_coverage:.0%}")
        cols = st.columns(5)
        cols[0].metric("Findings cited", f"{q.cited} / {q.findings}")
        focus_label = f"About {short(', '.join(q.focus), 18)}" if q.focus else "On focus"
        cols[1].metric(
            focus_label,
            f"{q.on_focus} / {q.findings}",
            help="Findings that name the market or company asked about",
        )
        cols[2].metric("Source domains", len(q.domains))
        cols[3].metric("Full pages read", q.scraped_pages)
        cols[4].metric("Snippets used", q.search_snippets + q.sample_findings)
        if q.domains:
            st.caption("Domains: " + ", ".join(q.domains))
        if q.grounding_problems:
            st.error("Citation problems remain:\n\n- " + "\n- ".join(q.grounding_problems))
        else:
            st.success("Every observation cites a real finding.")

    critique = state.critique
    st.markdown("**Critic review**")
    if critique is None:
        st.caption("The Critic did not run.")
        return
    if critique.approved:
        st.success(f"Approved after {state.revisions_used} revision(s).")
    else:
        st.warning(f"Not approved after {state.revisions_used} revision(s).")
    for issue in critique.issues:
        st.markdown(f"- {issue}")
    if critique.revision_request and not critique.approved:
        st.caption(f"Last revision request: {critique.revision_request}")


def trace_tab(state: ResearchState) -> None:
    st.caption("Every handoff between agents, in order, with how long each step took.")
    for i, step in enumerate(state.trace, start=1):
        with st.container(border=True):
            left, right = st.columns([5, 1])
            left.markdown(f"**{i}. {step.agent}** · {step.action}")
            if step.duration_ms is not None:
                right.markdown(f"`{format_ms(step.duration_ms)}`")
            if step.detail:
                with st.expander("Details"):
                    st.json(step.detail, expanded=True)


def export_tab(state: ResearchState) -> None:
    st.caption("The Markdown brief is ready to share; the JSON holds the whole run.")
    col_md, col_json = st.columns(2)
    col_md.download_button(
        "Download brief (.md)",
        brief_to_markdown(state),
        file_name="research-brief.md",
        width="stretch",
    )
    col_json.download_button(
        "Download full run (.json)",
        json.dumps(state.model_dump(mode="json"), indent=2),
        file_name="research-run.json",
        width="stretch",
    )
    with st.expander("Preview Markdown"):
        st.code(brief_to_markdown(state), language="markdown")


def results(state: ResearchState, model_label: str) -> None:
    metric_row(state, model_label)
    tabs = st.tabs(["Brief", "Evidence", "Quality", "Agent trace", "Export"])
    with tabs[0]:
        brief_tab(state)
    with tabs[1]:
        evidence_tab(state)
    with tabs[2]:
        quality_tab(state)
    with tabs[3]:
        trace_tab(state)
    with tabs[4]:
        export_tab(state)
