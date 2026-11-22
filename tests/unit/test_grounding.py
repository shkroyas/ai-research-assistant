from market_research.grounding import check_grounding, cited_ids
from market_research.models import Brief, Competitor, Finding

FINDINGS = [
    Finding(id="F1", claim="Foodmandu launched in 2010", source_title="a"),
    Finding(id="F2", claim="Pathao Food operates in Kathmandu", source_title="b"),
]


def test_cited_ids_reads_single_and_grouped_citations() -> None:
    assert cited_ids("Growth is strong [F1] and rising [F2, F3]") == {"F1", "F2", "F3"}
    assert cited_ids("no citations here") == set()


def test_grounded_brief_has_no_problems() -> None:
    brief = Brief(
        summary="Two players lead [F1, F2].",
        competitors=[Competitor(name="Foodmandu", note="pioneer", finding_ids=["F1"])],
        observations=["Kathmandu is the core market [F2]"],
    )
    assert check_grounding(brief, FINDINGS) == []


def test_flags_uncited_and_invented_citations() -> None:
    brief = Brief(
        summary="Market is large [F9].",
        competitors=[Competitor(name="Ghost", note="?", finding_ids=[])],
        observations=["No source for this", "Made up [F7]"],
    )
    problems = check_grounding(brief, FINDINGS)
    assert any("no citation" in p for p in problems)
    assert any("unknown finding F7" in p for p in problems)
    assert any("Summary cites unknown finding F9" in p for p in problems)
    assert any("'Ghost' has no supporting finding" in p for p in problems)


def test_masked_figures_are_flagged() -> None:
    from market_research.models import Brief, Finding

    findings = [Finding(id="F1", claim="x", source_title="A")]
    brief = Brief(summary="Revenue is US$ ****** million [F1].", observations=["Fact [F1]"])
    assert any("masked figure" in p for p in check_grounding(brief, findings))


def test_competitor_backed_only_by_background_is_flagged() -> None:
    from market_research.models import Brief, Competitor, Finding

    findings = [
        Finding(id="F1", claim="DoorDash leads the US", source_title="G", on_focus=False),
        Finding(id="F2", claim="Foodmandu leads Nepal", source_title="K"),
    ]
    brief = Brief(
        summary="s [F2]",
        observations=["o [F2]"],
        competitors=[
            Competitor(name="DoorDash", note="global", finding_ids=["F1"]),
            Competitor(name="Foodmandu", note="local", finding_ids=["F2"]),
        ],
    )
    problems = check_grounding(brief, findings)
    assert problems == [
        "Competitor 'DoorDash' is supported only by background findings that do not mention "
        "the focus"
    ]
