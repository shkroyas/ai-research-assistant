"""Deterministic evidence checks that run before and alongside the Critic.

The language model writes and judges text; plain code checks what code can:
every citation must point to a real finding, and every competitor must be
backed by evidence.
"""

import re

from market_research.evidence import MASKED
from market_research.models import Brief, Finding

CITATION_PATTERN = re.compile(r"\[(F\d+(?:\s*,\s*F\d+)*)\]")


def cited_ids(text: str) -> set[str]:
    """Return every finding id cited in text, e.g. 'grew fast [F1, F3]' -> {'F1', 'F3'}."""
    ids: set[str] = set()
    for group in CITATION_PATTERN.findall(text):
        ids.update(part.strip() for part in group.split(","))
    return ids


def check_grounding(brief: Brief, findings: list[Finding], kind: str = "market") -> list[str]:
    """Return human-readable problems; an empty list means the brief is grounded.

    For market and topic requests a competitor must be backed by a finding about the
    focus. For company and comparison requests a rival's own findings are enough.
    """
    known = {f.id for f in findings}
    problems: list[str] = []

    for observation in brief.observations:
        ids = cited_ids(observation)
        if not ids:
            problems.append(f"Observation has no citation: {observation!r}")
        for unknown in sorted(ids - known):
            problems.append(f"Observation cites unknown finding {unknown}: {observation!r}")

    for unknown in sorted(cited_ids(brief.summary) - known):
        problems.append(f"Summary cites unknown finding {unknown}")

    for competitor in brief.competitors:
        if not competitor.finding_ids:
            problems.append(f"Competitor {competitor.name!r} has no supporting finding")
        for unknown in sorted(set(competitor.finding_ids) - known):
            problems.append(f"Competitor {competitor.name!r} cites unknown finding {unknown}")

    texts = [brief.summary, *brief.observations, *(c.note for c in brief.competitors)]
    if any(MASKED.search(text) for text in texts):
        problems.append("Brief quotes a redacted or masked figure (e.g. 'US$ ****')")

    by_id = {f.id: f for f in findings}
    for competitor in brief.competitors if kind in ("market", "topic") else []:
        support = [by_id[i] for i in competitor.finding_ids if i in by_id]
        if support and not any(f.on_focus for f in support):
            problems.append(
                f"Competitor {competitor.name!r} is supported only by background findings "
                "that do not mention the focus"
            )

    return problems
