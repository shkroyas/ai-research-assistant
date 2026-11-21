# 004 Deeper evidence and a complete app: design

## Data flow

```text
query
  └─ Researcher
       ├─ plan 2-4 searches (model)
       ├─ search (Tavily or sample data)        → snippets with URLs
       ├─ scrape result pages in parallel        → readable text per page
       │     robots.txt → GET (timeout, size cap, HTML only) → strip boilerplate
       ├─ choose the most relevant passage per page (keyword overlap with the query)
       └─ findings F1..F10  (claim, domain, evidence = scraped page | search snippet | sample data)
  └─ Analyst → Critic (unchanged; they simply see better evidence)
  └─ quality report (code) + timings in the trace
```

## Scraper (`scraper.py`)

| Concern | Choice | Why |
| --- | --- | --- |
| HTTP | `httpx.Client`, follows redirects, 8 s timeout | Already a dependency of the model SDKs. Supports a mock transport for tests. |
| Parsing | BeautifulSoup with the built-in `html.parser` | Tolerant of broken HTML, with no compiled dependency. |
| Boilerplate | Drop `script`, `style`, `noscript`, `nav`, `header`, `footer`, `aside`, `form`, `svg`, `iframe`. Prefer `<article>` or `<main>` when present. | Simple rules that cover most news and blog pages. |
| Passage choice | Split into paragraphs of 60 characters or more. Score each by the query terms it contains (stop words removed), with a small bonus for numbers. Keep the best paragraph, trimmed to 600 characters. | Easy to explain and test, and fast. No embedding model is needed. |
| Politeness | `urllib.robotparser` per domain, cached for the run. A descriptive User-Agent. At most 4 parallel workers. | Respects site owners' rules. |
| Limits | Read at most 2 MB, and only `text/html` or `application/xhtml+xml`. | Protects memory and avoids PDFs and binaries. |
| Failure | Return `ScrapeResult(ok=False, reason=...)` and never raise. | One bad site must not fail a brief. |

`PageScraper` has the same shape as the search providers: a small class with one public method (`scrape_many(urls, query)`) and a constructor that accepts an `httpx.Client`, so tests inject a `MockTransport`.

## Model changes

- `Finding` gains `evidence: Literal["scraped page", "search snippet", "sample data"]` and `domain: str | None`.
- `StepLog` gains `duration_ms: int | None`.
- `ResearchState` gains `duration_ms`.
- `quality.py` adds `QualityReport.from_state(state)`. It is pure code, uses the existing `cited_ids` and `check_grounding`, and is stored on the state when the run finishes.

## Timing

The Orchestrator wraps each agent call with `time.perf_counter()` and writes `duration_ms` on that step's last trace entry. This needs no changes to the agents.

## UI structure (`app/`)

```text
streamlit_app.py      page flow: sidebar → hero or results
ui/components.py      metric row, brief card, evidence table, trace timeline, quality panel
ui/text.py            citation links ([F1] → [F1](url)), domain labels
.streamlit/config.toml theme
```

- Splitting the UI into components keeps `streamlit_app.py` short and lets each component be tested through AppTest.
- Run history lives in `st.session_state["history"]` (newest first, at most 10). Choosing a run from the sidebar re-renders it without calling the model.
- The workflow is drawn with `st.graphviz_chart`, which is built into Streamlit, so no image files or extra packages are needed.

## Rejected alternatives

- **Headless browser scraping (Playwright).** It can render JavaScript, but adds a large browser dependency to the image and is slow. Static HTML covers the news, report and blog pages that search returns.
- **Embedding-based passage choice.** It needs a second model and more cost. Keyword overlap is good enough for short passages and is easy to test.
- **Tavily's own `include_raw_content`.** It ties the evidence to one provider. A separate scraper also works with any future search provider.
