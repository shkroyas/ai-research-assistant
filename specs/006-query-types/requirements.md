# 006 Query types: requirements

Status: done

## Why

Spec 005 tuned the Researcher for one shape of request, "a market in a place" (for example *food delivery in Nepal*). Users also ask about a company, compare companies, or ask about a topic or trend with no place at all. With only one shape in mind:

1. **Company requests fail the checks.** For "Research Tesla", a finding about BYD does not mention Tesla, so a BYD competitor was flagged as "background only" and blocked approval.
2. **Search plans are always market plans.** The prompt always asked for market size, local players and regulation, even when the user asked about one company's strategy or a comparison.
3. **"Global" became a focus.** A request such as "global EV battery market" could give the focus `["global"]`, and every source had to contain that word.
4. **The Analyst always wrote a market brief**, whatever was asked.

## Acceptance criteria

### R1 Understand the request

- **R1.1** The search plan includes the request type: `market` (an industry, optionally in a place), `company` (one company), `comparison` (two or more named companies or products) or `topic` (a trend, technology or question). An unknown type from the model becomes `market`.
- **R1.2** When planning fails, code guesses the type: `comparison` for "compare", "vs" or "versus", otherwise `market`.
- **R1.3** Words that mean "everywhere" (global, worldwide, world, international) are never focus terms. A global request has no focus, so no source is marked background.

### R2 Search for what was asked

- **R2.1** The Researcher prompt gives search guidance for each type (for example strategy, products and financials for a company; head-to-head facts for a comparison; adoption, drivers and risks for a topic).

### R3 Answer what was asked

- **R3.1** The Analyst and Critic see the request type and adapt the brief: for a company, competitors are its rivals; for a comparison, the compared companies are the competitors; for a topic, competitors are the leading companies in it, if the findings name any.
- **R3.2** The "background-only competitor" check applies only to `market` and `topic` requests. For `company` and `comparison` requests, a rival is supported by findings about the rival itself.

### R4 Visibility

- **R4.1** The request type is shown in the trace, the quality report and the app.
- **R4.2** The app offers examples of each type.

### R5 Tests

- **R5.1** Offline tests cover type parsing and fallback, removal of global words from the focus, the competitor rule per type, and the type reaching the Analyst prompt.

## Traceability

| Criterion | Code | Tests |
| --- | --- | --- |
| R1.1 | `researcher.SearchPlan` | `test_unknown_kind_becomes_market`, `test_plan_keeps_model_kind_and_focus` |
| R1.2 | `evidence.fallback_kind` | `test_fallback_kind_spots_comparisons` |
| R1.3 | `evidence.clean_focus` | `test_clean_focus_drops_global_words`, `test_global_request_has_no_background` |
| R2.1 | `prompts.RESEARCHER_SYSTEM` | `test_plan_keeps_model_kind_and_focus` |
| R3.1 | `prompts.ANALYST_SYSTEM`, `prompts.CRITIC_SYSTEM`, `analyst.focus_line` | `test_analyst_prompt_names_focus_and_labels_background` |
| R3.2 | `grounding.check_grounding` | `test_competitor_backed_only_by_background_is_flagged`, `test_company_requests_allow_rivals_from_their_own_findings` |
| R4.1 | `ResearchState.kind`, `quality.assess`, `ui.components` | `test_assess_counts_findings_about_the_focus`, `test_run_shows_metrics_and_all_result_tabs` |
| R4.2 | `streamlit_app.EXAMPLES` | `test_landing_page_explains_agents_and_offers_examples` |
