import pytest
from pydantic import ValidationError

from market_research.models import Brief, Competitor, Finding, ResearchState


def test_brief_keeps_at_most_two_competitors() -> None:
    competitors = [Competitor(name=f"C{i}", note="n") for i in range(3)]
    brief = Brief(summary="s", competitors=competitors)  # extras are trimmed, not fatal
    assert [c.name for c in brief.competitors] == ["C0", "C1"]


def test_brief_drops_blank_lines_and_query_drops_control_characters() -> None:
    brief = Brief(summary="s", observations=["a [F1]", "  ", ""], missing_information=[""])
    assert (brief.observations, brief.missing_information) == (["a [F1]"], [])
    assert ResearchState(query="EV\x00 market\n in  Nepal").query == "EV market in Nepal"


def test_brief_round_trips_through_json() -> None:
    brief = Brief(
        summary="Food delivery in Nepal is growing.",
        competitors=[Competitor(name="Foodmandu", note="Early leader", finding_ids=["F1"])],
        observations=["Demand is concentrated in Kathmandu [F1]"],
        sources=["F1: Example source"],
        missing_information=["Market size in NPR"],
    )
    assert Brief.model_validate_json(brief.model_dump_json()) == brief


def test_finding_id_must_look_like_citation() -> None:
    with pytest.raises(ValidationError):
        Finding(id="source-1", claim="c", source_title="t")


def test_state_rejects_blank_query() -> None:
    with pytest.raises(ValidationError):
        ResearchState(query="   ")


def test_state_log_appends_trace_and_flags_sample_data() -> None:
    state = ResearchState(query="  Food delivery in Nepal ")
    assert state.query == "Food delivery in Nepal"
    state.findings.append(Finding(id="F1", claim="c", source_title="t", is_sample_data=True))
    state.log("Researcher", "collected findings", count=1)
    assert state.uses_sample_data is True
    assert state.trace[0].agent == "Researcher"
    assert state.trace[0].detail == {"count": 1}
