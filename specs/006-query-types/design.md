# 006 Query types: design

```text
plan (model) ─► kind + focus + queries
              ├─ kind: market | company | comparison | topic   (unknown → market; fallback: "vs"/"compare" → comparison)
              └─ focus: global words removed (code)
Researcher ─► same ranking as spec 005 (an empty focus means everything is on focus)
Analyst / Critic prompt: "Request type: company" + "Focus: Tesla" ─► type-specific rules
grounding: background-only competitor rule only for market and topic requests
```

- **One extra field, not four pipelines.** The type is a single field in the existing plan, so every agent stays the same shape and the brief schema does not change. Only the prompts and one code rule look at it.
- **The model decides the type, code keeps it safe.** The model reads intent better than a rule. Code normalises unknown values and guesses a type when planning fails, so a run never breaks on it.
- **Why the competitor rule depends on the type.** For a market request, a competitor must be shown to operate in the asked market, so its finding must mention the focus. For a company request, the rival's own findings are the right evidence even when they do not name the company asked about.
