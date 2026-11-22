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
# Markdown bold such as "**Foodmandu**": the stars hug the text, unlike "US$ ****".
BOLD = re.compile(r"\*\*(?=[^\s*])(.+?)(?<=[^\s*])\*\*")
TABLE_RULE = re.compile(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
MAX_BACKGROUND = 3
# Icon-font ligatures and emoji that leak into page text, e.g. "arrow_forward 🍔".
ICON_WORDS = re.compile(
    r"\b(?:arrow_(?:forward|back|upward|downward|drop_down)|chevron_(?:left|right)|"
    r"expand_(?:more|less)|keyboard_arrow_\w+|open_in_new|more_vert)\b"
)
EMOJI = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf\ufe0f\u200d]")
FUNCTION_WORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "has", "have", "in", "is",
    "it", "its", "of", "on", "or", "that", "the", "their", "to", "was", "were", "which",
    "with",
}  # fmt: skip
# Social posts are weak evidence: they are kept, but ranked after other sources.
SOCIAL_DOMAINS = (
    "facebook.com", "instagram.com", "tiktok.com", "twitter.com", "x.com",
    "pinterest.com", "threads.net",
)  # fmt: skip
# Words that mean "everywhere": a request about the whole world has no focus.
GLOBAL_WORDS = {"global", "globally", "world", "worldwide", "international", "the world"}
COMPARISON = re.compile(r"\b(compare|comparison|versus|vs\.?)\b", re.IGNORECASE)

# Words that start a request rather than name a place or company.
NOT_NAMES = {
    "analyse", "analyze", "assess", "compare", "describe", "explain", "give", "global", "how",
    "industry", "market", "research", "show", "summarise", "summarize", "tell", "the",
    "what", "which", "who", "why",
}  # fmt: skip


def unbold(text: str) -> str:
    """'**Foodmandu** leads' -> 'Foodmandu leads'; masked figures are left alone."""
    return BOLD.sub(r"\1", text)


def has_masked(text: str) -> bool:
    """True for redacted figures ('US$ ****', '██'), but not for markdown bold."""
    return bool(MASKED.search(unbold(text)))


def clean_evidence(text: str) -> str:
    """Drop sentences with masked figures and strip table, heading and bullet noise."""
    text = TABLE_RULE.sub(" ", unbold(text))
    text = re.sub(r"(^|\s)#{1,6}\s", " ", text)
    text = text.replace("|", " ").replace("▲", " ").replace("▼", " ")
    text = EMOJI.sub(" ", ICON_WORDS.sub(" ", text))
    text = " ".join(text.split())
    sentences = [s for s in SENTENCE_END.split(text) if s and not MASKED.search(s)]
    text = " ".join(sentences).strip(" -•")
    return text if looks_like_prose(text) else ""


def looks_like_prose(text: str) -> bool:
    """False for menus, table headers and lists of labels, which read like
    'Rank Company Details Short Description Total Funding'. Short texts pass."""
    words = re.findall(r"[a-z]+", text.lower())
    if len(words) < 12:
        return True
    return sum(w in FUNCTION_WORDS for w in words) / len(words) >= 0.06


def is_social(url: str | None) -> bool:
    """True for social media posts, e.g. https://www.facebook.com/..."""
    match = re.match(r"https?://([^/]+)", url or "")
    host = match.group(1).lower() if match else ""
    return any(host == d or host.endswith("." + d) for d in SOCIAL_DOMAINS)


def fallback_focus(query: str) -> list[str]:
    """Capitalised names in the query, e.g. 'Food delivery in Nepal' -> ['Nepal'].

    The first word is capitalised only because it starts the sentence, so it counts as
    a name only when the query names nothing else ('Tesla market share' -> ['Tesla']).
    """
    groups = []
    for match in re.finditer(r"\b[A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*)*", query):
        words = [w for w in match.group().split() if w.lower() not in NOT_NAMES]
        if words:
            groups.append((match.start() == len(query) - len(query.lstrip()), words))
    if len(groups) > 1 and groups[0][0]:
        rest = groups[0][1][1:]
        groups = ([(False, rest)] if rest else []) + groups[1:]
    return [" ".join(words) for _, words in groups]


def clean_focus(focus: Iterable[str]) -> list[str]:
    """Strip, de-duplicate and drop words that mean 'everywhere' from focus terms."""
    kept: list[str] = []
    for term in focus:
        term = " ".join(term.split())
        if term and term.lower() not in GLOBAL_WORDS and term.lower() not in map(str.lower, kept):
            kept.append(term)
    return kept


def named_in(query: str, term: str) -> bool:
    return bool(re.search(rf"\b{re.escape(term.lower())}\b", query.lower()))


def settle_kind(query: str, kind: str, focus: list[str]) -> tuple[str, list[str]]:
    """Correct the model's request type and focus where the query clearly disagrees.

    - A company or comparison is about the names the user wrote. Rivals the model
      added to the focus are dropped (they belong in the brief, not the focus).
    - A 'comparison' that names only one company and has no 'vs' or 'compare' is
      a company request, e.g. "Research Tesla and its main competitors".
    """
    if kind not in ("company", "comparison"):
        return kind, focus
    named = [term for term in focus if named_in(query, term)]
    if kind == "comparison" and len(named) < 2 and not COMPARISON.search(query):
        kind = "company"
    return kind, named or focus


def fallback_kind(query: str) -> str:
    """Guess the request type when planning fails: comparisons are easy to spot."""
    return "comparison" if COMPARISON.search(query) else "market"


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
    on_focus = sorted((m for m in marked if m[1]), key=lambda m: is_social(m[0].url))
    background = [m for m in marked if not m[1]][:max_background]
    return (on_focus + background)[:limit]
