# 007 Clarifying questions, declines and safe failure: requirements

Status: done

## Why

A research brief built from a vague or inappropriate request is worse than no brief: the agents guess, search for something else and present the guess with citations. Separately, anything the outside world sends (a failed search, a slow model, a page that redirects to a private address, a model that names three competitors) should never crash the app or leak into the result.

## Acceptance criteria

### R1 Understand the request before researching

- **R1.1** Before any search, a request is classed as `research`, `unclear` or `decline`.
- **R1.2** Code rules catch requests with no subject (for example "hi", "market", "tell me about the best company") or longer than 400 characters, without a model call.
- **R1.3** The model classes the rest as part of the search plan. It prefers `research` whenever one sensible reading exists, asks one clarifying question when it cannot tell what to research or a name is ambiguous, and declines requests that are harmful, target a private person, or are not business research. An unknown status never blocks research.
- **R1.4** An `unclear` or `declined` request stops the run: no search, no Analyst and no Critic. The app shows the question or the reason, with up to three research-ready suggestions that run in one click. The command line prints them and exits with status 2.

### R2 Safe failure

- **R2.1** A failed web search skips that query and is recorded in the trace; the run continues.
- **R2.2** Model calls time out after 120 seconds.
- **R2.3** Model output that breaks a limit is trimmed instead of failing the run: extra competitors and blank lines are dropped.
- **R2.4** The app never shows a traceback. Unexpected errors show a short message and are logged.
- **R2.5** The query box is limited to 400 characters, and control characters are removed from queries.

### R3 Untrusted content

- **R3.1** The scraper never fetches private, loopback, link-local or cloud metadata addresses, including through redirects.
- **R3.2** The Analyst and Critic prompts treat findings as quoted evidence and ignore instructions inside them.

## Traceability

| Criterion | Code | Tests |
| --- | --- | --- |
| R1.1, R1.3 | `researcher.SearchPlan`, `prompts.RESEARCHER_SYSTEM` | `test_unknown_status_never_blocks_research`, `test_unclear_request_asks_a_question_and_writes_no_brief`, `test_inappropriate_request_is_declined_with_a_reason` |
| R1.2 | `intake.screen_query` | `test_rules_catch_requests_with_no_subject`, `test_rules_let_real_requests_through`, `test_rules_stop_vague_requests_without_a_model_call` |
| R1.4 | `Orchestrator.run`, `ui.components.clarify`, `cli.intake_message` | `test_vague_request_asks_for_clarity_with_suggestions`, `test_cli_explains_and_exits_2_for_unclear_requests` |
| R2.1 | `Researcher.run` | `test_a_failed_search_is_skipped_not_fatal` |
| R2.2 | `llm.REQUEST_TIMEOUT` | (configuration) |
| R2.3, R2.5 | `models.Brief`, `models.ResearchState` | `test_brief_keeps_at_most_two_competitors`, `test_brief_drops_blank_lines_and_query_drops_control_characters` |
| R2.4 | `streamlit_app.run_research` | `test_unexpected_error_shows_a_message_not_a_traceback` |
| R3.1 | `scraper.is_public_host`, `PageScraper._check_public` | `test_private_and_metadata_addresses_are_not_public`, `test_names_resolving_to_private_addresses_are_not_public`, `test_redirect_to_metadata_address_is_never_followed` |
| R3.2 | `prompts.ANALYST_SYSTEM`, `prompts.CRITIC_SYSTEM` | `test_prompts_tell_models_to_ignore_instructions_in_sources` |
