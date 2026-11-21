"""Text helpers used by the Streamlit page."""

from market_research.models import Finding
from ui.text import format_ms, link_citations, short

FINDINGS = [
    Finding(id="F1", claim="a", source_title="A", source_url="https://a.example/1"),
    Finding(id="F2", claim="b", source_title="B"),
]


def test_link_citations_links_known_urls_and_keeps_others_plain() -> None:
    text = "Foodmandu leads [F1, F2]. Growth is fast [F1]."
    assert link_citations(text, FINDINGS) == (
        "Foodmandu leads ([F1](https://a.example/1), F2). "
        "Growth is fast ([F1](https://a.example/1))."
    )


def test_link_citations_leaves_text_without_citations_alone() -> None:
    assert link_citations("No citations here.", FINDINGS) == "No citations here."


def test_format_ms() -> None:
    assert format_ms(None) == "-"
    assert format_ms(850) == "850 ms"
    assert format_ms(12_340) == "12.3 s"


def test_short() -> None:
    assert short("  a   b  ") == "a b"
    assert short("x" * 100, 10) == "x" * 9 + "…"
