# 004 Deeper evidence and a complete app: requirements

**Status:** In progress.

## Goal

Search snippets are short and sometimes out of context. Read the source pages themselves, so the Analyst works from the most relevant passage on each page. Then make the quality of every brief visible, and turn the Streamlit page into a complete research tool, not a demo.

## Acceptance criteria

### R1 Page scraping

- **R1.1** After search, the Researcher fetches the source page of each result and extracts its readable text. Scripts, styles, navigation, headers, footers and forms are removed.
- **R1.2** From each page it keeps the passage most relevant to the query, at most 600 characters. This passage replaces the search snippet as the finding's claim.
- **R1.3** Before fetching a page, it reads the site's `robots.txt` and skips the page if fetching is disallowed. Requests identify the app with a descriptive User-Agent.
- **R1.4** Each fetch has a timeout, skips responses that are not HTML, and stops reading after a size limit.
- **R1.5** Pages are fetched in parallel with a small worker limit, so scraping five pages takes about as long as the slowest one.
- **R1.6** If a page cannot be used for any reason, the finding keeps the search snippet, and the reason is recorded in the trace. Scraping never fails a run.
- **R1.7** Each finding records how its text was obtained (`scraped page`, `search snippet` or `sample data`) and its source domain.
- **R1.8** Scraping can be switched off with `SCRAPE_PAGES=false` and in the UI. Sample data is never scraped.

### R2 Quality report

- **R2.1** Every run produces a quality report computed in code, not by the model:
  - findings collected and findings cited;
  - citation coverage (cited findings as a share of all findings);
  - distinct source domains;
  - pages scraped versus snippets used;
  - grounding problems that remain.
- **R2.2** The trace records the duration of each agent step and of the whole run.

### R3 Streamlit app

- **R3.1** The landing page explains the four agents and the workflow, and offers example queries that run with one click.
- **R3.2** While a run is in progress, the page shows each agent's step as it completes, with a progress bar.
- **R3.3** Results open with headline metrics: model, findings, sources, citation coverage, Critic verdict and run time.
- **R3.4** Results are organised in tabs:
  - **Brief**: citations link to their source pages.
  - **Evidence**: a table of findings with domain, how each was obtained and whether the brief cites it.
  - **Quality**: the report from R2 and the Critic's review.
  - **Agent trace**: a timeline of every handoff with durations.
  - **Export**: the Markdown and JSON downloads.
- **R3.5** The sidebar holds the model picker, web search status, a scraping switch and search depth. It also lists earlier runs from this session, which can be reopened.
- **R3.6** The page uses a consistent theme and works at narrow widths.

### R4 Tests

- **R4.1** The scraper is tested offline with a mock HTTP transport. The tests cover text extraction, passage choice, a `robots.txt` refusal, non-HTML content, the size limit, timeouts and HTTP errors.
- **R4.2** The Researcher is tested with a fake scraper: scraped passages are used, and the snippet is kept as the fallback.
- **R4.3** The quality report, citation links and step timings have unit tests.
- **R4.4** Streamlit AppTest covers the tabs, the example-query buttons and run history.

## Out of scope

- Crawling beyond the result pages, rendering JavaScript, and bypassing paywalls or logins.
- Persisting run history across browser sessions.
