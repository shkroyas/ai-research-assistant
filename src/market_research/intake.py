"""Cheap checks on a request before any model or search is used.

The Researcher's planning step asks the model whether a request is clear and
appropriate. These rules catch the obvious cases (an empty phrase, a greeting,
a whole document pasted in) without spending a model call.
"""

import re

from market_research.models import Intake

MAX_QUERY_CHARS = 400
SUGGESTIONS = [
    "Analyze the food delivery market in Nepal",
    "Research Tesla and its main competitors",
    "AI adoption in banking",
]
# Words that carry no subject on their own: requests, greetings and generic nouns.
EMPTY_WORDS = {
    "a", "about", "analyse", "analysis", "analyze", "and", "any", "anything", "best",
    "business", "can", "company", "companies", "data", "do", "for", "give", "good", "hello",
    "help", "hey", "hi", "i", "industry", "info", "information", "is", "it", "me", "market",
    "markets", "my", "of", "ok", "on", "please", "report", "research", "show", "something",
    "stuff", "tell", "test", "thanks", "that", "the", "thing", "things", "this", "to", "top",
    "what", "you",
}  # fmt: skip


def screen_query(query: str) -> Intake | None:
    """Return an Intake when the request is clearly unusable, otherwise None."""
    if len(query) > MAX_QUERY_CHARS:
        return Intake(
            status="unclear",
            reason=f"The request is longer than {MAX_QUERY_CHARS} characters.",
            question="What is the one market, company or topic you want researched?",
            suggestions=SUGGESTIONS,
        )
    words = re.findall(r"[a-z0-9][a-z0-9&'.-]*", query.lower())
    if not [w for w in words if w not in EMPTY_WORDS and len(w) > 1]:
        return Intake(
            status="unclear",
            reason="The request does not name a market, company or topic.",
            question="What market, company or topic should I research, and where?",
            suggestions=SUGGESTIONS,
        )
    return None
