# 005 Market focus and evidence hygiene: design

```text
plan (model) ─► focus terms + queries ─► ensure every query names the focus (code)
search ─► clean text (code) ─► drop empty ─► mark on-focus (code)
       ─► rank: on-focus first, background capped at 3 ─► scrape (prefers focus paragraphs)
Analyst prompt: focus + BACKGROUND labels ─► Brief
Critic: grounding (code) now also flags masked figures and background-only competitors
```

- **Focus terms come from the model, with a code fallback.** The model separates "Nepal" from "food delivery" better than a rule can. A capitalised-word fallback keeps runs working when planning fails.
- **The relevance test is a string match, on purpose.** "Does the source mention Nepal?" is cheap, explainable and testable. An embedding similarity score would be harder to justify in a review.
- **Background is capped, not dropped.** Global context is useful ("the global market grows about 9% a year"), but it must not crowd out local evidence or produce competitors.
- **Rules live in code where possible.** Masked figures and background-only competitors are deterministic checks in `grounding.py`, so they block approval even if the model misses them.
- **New module `evidence.py`** holds cleaning, focus matching and ranking, so the Researcher stays a short orchestration of steps.
