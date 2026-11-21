"""Small text helpers for the page, kept free of Streamlit so they are easy to test."""

from market_research.grounding import CITATION_PATTERN
from market_research.models import Finding


def link_citations(text: str, findings: list[Finding]) -> str:
    """Turn '[F1, F3]' into '([F1](url1), [F3](url3))' so each citation opens its source."""
    urls = {f.id: f.source_url for f in findings}

    def replace(match) -> str:
        ids = [part.strip() for part in match.group(1).split(",")]
        links = [f"[{i}]({urls[i]})" if urls.get(i) else i for i in ids]
        return f"({', '.join(links)})"

    return CITATION_PATTERN.sub(replace, text)


def format_ms(ms: int | None) -> str:
    if ms is None:
        return "-"
    return f"{ms} ms" if ms < 1000 else f"{ms / 1000:.1f} s"


def short(text: str, limit: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
