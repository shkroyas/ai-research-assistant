"""Evidence hygiene and focus: clean raw text, test relevance, rank results.

Everything here is plain code, so it is cheap, explainable and testable:
- clean_evidence removes masked figures and markup noise from snippets and passages;
- mentions_focus tells whether a source talks about the place or company asked about;
- rank_results puts on-focus results first and caps general background.
"""

import re
from collections.abc import Iterable

from market_research.search import SearchResult

MASKED = re.compile(r"\*{2,}|█")
TABLE_RULE = re.compile(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
MAX_BACKGROUND = 3

# Words that start a request rather than name a place or company.
NOT_NAMES = {
    "analyse", "analyze", "assess", "compare", "describe", "explain", "give", "how",
    "industry", "market", "research", "show", "summarise", "summarize", "tell", "the",
    "what", "which", "who", "why",
}  # fmt: skip


def clean_evidence(text: str) -> str:
    """Drop sentences with masked figures and strip table, heading and bullet noise."""
    text = TABLE_RULE.sub(" ", text)
    text = re.sub(r"(^|\s)#{1,6}\s", " ", text)
    text = text.replace("|", " ").replace("▲", " ").replace("▼", " ")
    text = " ".join(text.split())
    sentences = [s for s in SENTENCE_END.split(text) if s and not MASKED.search(s)]
    return " ".join(sentences).strip(" -•")


def fallback_focus(query: str) -> list[str]:
    """Capitalised names in the query, e.g. 'food delivery in Nepal' -> ['Nepal']."""
    names = []
    for group in re.findall(r"\b[A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*)*", query):
        kept = [w for w in group.split() if w.lower() not in NOT_NAMES]
        if kept:
            names.append(" ".join(kept))
    return names


def mentions_focus(texts: Iterable[str | None], focus: list[str]) -> bool:
    """True when any focus term appears (whole word, any case) in any of the texts."""
    if not focus:
        return True
    haystack = " ".join(t for t in texts if t).lower()
    return any(re.search(rf"\b{re.escape(term.lower())}\b", haystack) for term in focus)


def ensure_focus(queries: list[str], focus: list[str]) -> list[str]:
    """Make every search query name the focus, so search stays on the asked market."""
    if not focus:
        return queries
    return [q if mentions_focus([q], focus) else f"{q} {focus[0]}" for q in queries]


def rank_results(
    results: list[SearchResult],
    focus: list[str],
    limit: int,
    max_background: int = MAX_BACKGROUND,
) -> list[tuple[SearchResult, bool]]:
    """On-focus results first (search order kept), then at most `max_background` others."""
    marked = [(r, mentions_focus([r.title, r.url, r.content], focus)) for r in results]
    on_focus = [m for m in marked if m[1]]
    background = [m for m in marked if not m[1]][:max_background]
    return (on_focus + background)[:limit]
