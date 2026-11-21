# 004 Deeper evidence and a complete app: requirements

**Status:** Done.

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

## Traceability

| Criterion | Code | Tests |
| --- | --- | --- |
| R1.1, R1.2 | `scraper.extract_paragraphs`, `scraper.best_passage` | `test_extract_paragraphs_strips_boilerplate_and_prefers_article`, `test_best_passage_picks_most_relevant_paragraph`, `test_best_passage_trims_long_text_on_a_word_boundary` |
| R1.3 | `PageScraper._allowed`, `USER_AGENT` | `test_robots_txt_disallow_is_respected`, `test_robots_txt_forbidden_means_disallow_all`, `test_scrape_returns_relevant_passage_and_sends_user_agent` |
| R1.4 | `PageScraper._fetch_html` | `test_unusable_pages_report_a_reason`, `test_size_limit_stops_reading`, `test_timeout_and_network_errors_never_raise` |
| R1.5 | `PageScraper.scrape_many` | `test_scrape_many_deduplicates_and_reads_robots_once_per_site` |
| R1.6, R1.7 | `Researcher._scrape`, `models.Finding` | `test_scraped_passage_replaces_snippet_and_failures_keep_snippet`, `test_domain_is_exported_with_the_finding` |
| R1.8 | `config.scrape_pages`, `pipeline` | `test_sample_data_is_never_scraped`, `test_pipeline_attaches_scraper_only_when_enabled`, `test_sidebar_controls_reach_the_pipeline` |
| R2.1 | `quality.assess` | `test_assess_counts_coverage_domains_and_evidence_types`, `test_assess_ignores_invented_ids_and_reports_problems` |
| R2.2 | `Orchestrator.run` | `test_orchestrator_records_step_durations_and_quality` |
| R3.1 | `ui.components.hero` | `test_landing_page_explains_agents_and_offers_examples`, `test_example_button_runs_immediately` |
| R3.2 to R3.4 | `run_research`, `ui.components.results`, `ui.text.link_citations` | `test_run_shows_metrics_and_all_result_tabs`, `test_link_citations_links_known_urls_and_keeps_others_plain` |
| R3.5 | `sidebar`, run history | `test_history_keeps_earlier_runs_and_reopens_them`, `test_sidebar_controls_reach_the_pipeline` |
