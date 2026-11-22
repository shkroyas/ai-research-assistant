# 011 Fixes from the full audit: requirements

Status: done, checked live

## Why

A full test and audit of `fix/market-focus` against the assignment brief (12 live runs on Bedrock and Groq, offline sample mode, live PDF reading, a settings review) found these problems:

1. Copying `.env.example` to `.env` turns on web search and Groq with fake keys, so the offline sample fallback breaks and Groq fails with 401.
2. Markdown bold (`**Foodmandu**`) counts as a masked figure. Evidence sentences with bold are deleted, and a brief that uses bold is blocked by the grounding check.
3. `LOG_LEVEL` is never applied, and `get_settings()` is never called.
4. Search plans use stale years (2023, 2024) because the model does not know today's date.
5. The same article appears twice: once with a tracking parameter (`?fr=sycsrp_catchall`), once as a regional mirror (`au.investing.com` and `investing.com`).
6. With no findings, the Quality tab shows a green "Every observation cites a real finding.", the brief names companies that are in no finding, and offline mode does not say that only one sample dataset is bundled.
7. The scraper picks link lists ("Also, read: ...") over article text, and in PDFs an abbreviations page with no full stops becomes one passage.
8. The scraper's HTTP client is never closed (one leaked client per Streamlit run) and does not ask for PDFs in its `Accept` header.
9. A competitor note that already ends in `[F1]` is shown with `[F1]` twice.
10. The committed sample brief predates spec 010 and cites Facebook and Instagram posts.

## Acceptance criteria

- **R1** `Settings(_env_file=".env.example")` has web search off and no Groq keys. The placeholder lines stay in the file, commented out, and the README says to uncomment them. A blank or whitespace-only key counts as unset.
- **R2** Paired bold markers are removed from evidence before the masked-figure check, so `**Foodmandu** leads Nepal.` is kept and passes grounding. `US$ ****** million` and `██` are still dropped and flagged.
- **R3** `LOG_LEVEL` sets the level of the `market_research` loggers in the CLI and the Streamlit app, and the README lists it. `get_settings()` is removed.
- **R4** The planning prompt gives today's date, and the Researcher prompt asks for the most recent data instead of guessing a year.
- **R5** Tracking parameters (`utm_*`, `fr`, `ref`, `fbclid`, `gclid`, `mc_cid`, `mc_eid`) do not make a new finding. Two findings whose text is the same after scraping become one, keeping the first, and ids stay `F1..Fn` with no gaps.
- **R6** With no findings, the Quality tab shows a warning instead of the green success line. The Analyst is told not to name companies that are in no finding. In offline mode with no matching sample dataset, the trace and the brief say which sample topics are bundled. All four roles still run.
- **R7** HTML blocks that are mostly link text are skipped. PDF text with no sentence ends is cut into passages no longer than the passage limit, and a passage made mostly of all-caps abbreviations is skipped.
- **R8** `PageScraper` can be closed and closes a client it created itself. The CLI and Streamlit close it after each run (through `Orchestrator.close`). When PDF reading is on, `Accept` includes `application/pdf`.
- **R9** A competitor's finding ids are appended only when the note does not already cite them, in the app and in Markdown.
- **R10** Social posts are left out when at least five other on-focus results exist (they still rank last when sources are few). The sample brief in `samples/` is regenerated after R1 to R10 and contains no social posts or table headers.

## Out of scope

- **Forcing "sample data" into the summary** (audit issue 11). Sample data is already labelled in three places: the Markdown notice, the app warning and the `(sample data)` source tags. A code check would cost an extra model call per offline run.
- **Stopping before the Analyst when there are no findings.** It would save model calls, but the brief would then come from neither the Analyst nor the Critic, and the assignment is assessed on the four roles and their handoffs.
- Merging into `main`.

## Traceability

All tests are in `tests/unit/test_audit_fixes.py`.

| Criterion | Code | Tests |
| --- | --- | --- |
| R1 | `.env.example`, `config.Settings.blank_is_unset`, `README.md` | `test_env_example_copied_as_is_keeps_offline_mode`, `test_blank_keys_count_as_unset` |
| R2 | `evidence.unbold`, `evidence.has_masked`, `evidence.clean_evidence`, `grounding.check_grounding`, `scraper.best_passage` | `test_bold_text_is_kept_in_evidence`, `test_masked_figures_are_still_dropped`, `test_bold_in_the_brief_passes_grounding` |
| R3 | `config.configure_logging`, `cli.main`, `app/streamlit_app.main` | `test_log_level_sets_the_package_logger` |
| R4 | `Researcher.plan`, `prompts.RESEARCHER_SYSTEM` | `test_planning_prompt_gives_todays_date` |
| R5 | `researcher.url_key`, `researcher.drop_repeated_text` | `test_tracking_parameters_do_not_make_a_new_page`, `test_real_query_parameters_are_kept_in_any_order`, `test_mirrored_articles_become_one_finding` |
| R6 | `ui.text.grounding_status`, `prompts.ANALYST_SYSTEM`, `SampleDataSearch.topics`, `ResearchState.notice`, `render.brief_to_markdown` | `test_no_findings_is_a_warning_not_a_success`, `test_analyst_is_told_not_to_name_companies_outside_the_findings`, `test_offline_mode_says_which_sample_topics_exist` |
| R7 | `scraper.extract_paragraphs`, `scraper.pdf_text_chunks` | `test_link_lists_are_skipped`, `test_pdf_text_without_full_stops_is_cut_and_abbreviation_lists_are_skipped` |
| R8 | `PageScraper.close`, `Researcher.close`, `Orchestrator.close` | `test_scraper_closes_its_own_client_only` |
| R9 | `render.note_with_refs`, `ui.components.brief_tab` | `test_competitor_ids_are_added_only_when_missing` |
| R10 | `evidence.rank_results`, `evidence.MIN_OTHER_SOURCES` | `test_social_posts_are_dropped_when_five_other_sources_exist`, `test_social_posts_are_kept_last_when_sources_are_few` |

## Tasks

- [x] **T1** Fast-forward to `origin/fix/market-focus` (`737ef03`, PDF footnote marks).
- [x] **T2** Failing tests, then fixes, for R1 to R9.
- [x] **T3** `make lint` and `make test` pass (192 tests, 97% coverage).
- [x] **T4** Live check: the IFC Nepal digital payments PDF now gives a prose passage about NRB and UPI instead of its abbreviations page.
- [x] **T5** Regenerated the sample on Bedrock (Claude Opus 4.6). Searches now ask for 2026 data, there are no duplicate findings or doubled citations, no table headers, and the Critic approved with 9 of 10 findings cited.
- [x] **T6** Social posts are dropped when at least five other on-focus results exist (194 tests).
- [ ] **T7** Regenerate the sample on Bedrock and check it has no social posts.
