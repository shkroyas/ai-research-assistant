# 007 Clarifying questions, declines and safe failure: design

```text
query ─► rules (code): no subject / too long? ──yes──► unclear + suggestions ─┐
          │ no                                                                 │
          ▼                                                                    ▼
      plan (model): status + kind + focus + queries ── unclear / decline ──► stop: ask or explain
          │ research
          ▼
      search (each query guarded) ─► scrape (public addresses only) ─► Analyst ─► Critic
```

- **No extra model call.** The status is three more fields in the plan the Researcher already asks for, so clear requests cost nothing extra.
- **Rules first, model second.** Rules only catch the obvious cases, so they cannot wrongly block a real request; one-word subjects such as "Tesla" pass.
- **Bias towards answering.** Asking too often is as unhelpful as guessing. The prompt tells the model to research any request with one sensible reading and to state the scope it chose.
- **Stopping is a normal result, not an error.** The Orchestrator returns the state with the question or reason, so the app, the command line and the trace all show the same thing.
- **The scraper checks every request it sends** through an httpx request hook, so a redirect cannot reach a private address, and the check is testable with an injected resolver.
