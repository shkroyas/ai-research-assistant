# 001 Research brief: requirements

**Status:** Done. Delivered in PRs #1 to #8.

## Goal

A user types a company or an industry and receives a short, sourced research brief produced by four cooperating agents.

## Acceptance criteria

### R1 User interface

- **R1.1** A Streamlit page offers a text input for a company or industry and a **Run research** button.
- **R1.2** A blank query shows a warning and starts no agents.
- **R1.3** While agents run, the page shows each completed step.
- **R1.4** The user can choose the model (Claude on Bedrock or Groq). Groq is offered only when at least one key is configured.
- **R1.5** The finished brief can be downloaded as Markdown, and the full run as JSON.

### R2 Agents

- **R2.1** Four roles run in order: Orchestrator, Researcher, Analyst, Critic.
- **R2.2** The Researcher gathers evidence with web search, or uses sample data that is labelled as such in the data model, the UI and the export.
- **R2.3** The Analyst writes the brief only from the Researcher's findings and cites each claim by finding id.
- **R2.4** The Critic either approves the brief or requests a revision. The Analyst revises at most once, and code enforces this limit.

### R3 Structured handoffs

- **R3.1** The query, findings, draft brief and critique move between roles as one validated Pydantic object.
- **R3.2** Invalid model output is caught at the boundary and retried once with the validation error before failing.

### R4 Brief content

- **R4.1** The brief contains a summary, at most two competitors, key observations, and sources plus missing information.
- **R4.2** Every observation cites at least one existing finding. Invalid or missing citations block approval in code.
- **R4.3** The sources list is built in code from the findings actually cited.

### R5 Providers

- **R5.1** Claude runs on Amazon Bedrock through the InvokeModel API.
- **R5.2** Groq rotates across several keys. On HTTP 429 it switches key at once, and backs off only when every key is limited, honouring `retry-after`.
- **R5.3** On HTTP 401 or 403 the rejected Groq key is disabled for the session and the next key is used without waiting.

### R6 Engineering

- **R6.1** No secrets are committed. Configuration lives in `.env`, with a placeholder-only `.env.example`.
- **R6.2** The test suite runs offline with no keys, and CI runs lint and tests on every pull request.

## Traceability

| Criterion | Code | Tests |
| --- | --- | --- |
| R1.1, R1.3, R1.5 | `app/streamlit_app.py` | `test_run_shows_metrics_and_all_result_tabs` |
| R1.2 | `app/streamlit_app.py` | `test_blank_query_shows_warning` |
| R1.4 | `llm.available_providers`, sidebar | `test_model_picker_offers_claude_and_groq`, `test_groq_is_only_offered_with_keys` |
| R2.1 | `agents/orchestrator.py` | `test_happy_path_runs_roles_in_order` |
| R2.2 | `search.py`, `render.py` | `test_sample_search_labels_every_result`, `test_offline_run_with_labelled_sample_data`, `test_markdown_flags_sample_data_and_open_critic_notes` |
| R2.3 | `agents/analyst.py`, `prompts.py` | `test_analyst_drafts_brief_and_builds_sources_in_code` |
| R2.4 | `agents/orchestrator.py`, `config.py` | `test_one_revision_then_approval`, `test_never_more_than_one_revision`, `test_max_revisions_is_capped_at_one` |
| R3.1 | `models.py` | `test_brief_round_trips_through_json`, `test_state_rejects_blank_query` |
| R3.2 | `llm.complete_json` | `test_complete_json_retries_once_on_invalid_output`, `test_complete_json_raises_after_attempts` |
| R4.1 | `models.Brief` | `test_brief_allows_at_most_two_competitors`, `test_markdown_contains_all_brief_sections` |
| R4.2 | `grounding.py`, `agents/critic.py` | `test_flags_uncited_and_invented_citations`, `test_critic_overrides_model_approval_when_citations_are_invalid` |
| R4.3 | `agents/analyst.build_sources` | `test_analyst_drafts_brief_and_builds_sources_in_code` |
| R5.1 | `llm.BedrockClaudeClient` | `test_bedrock_invoke_client_is_default_and_builds_offline`, `test_bedrock_client_joins_text_and_handles_refusal` |
| R5.2 | `llm.GroqClient` | `test_groq_rotates_to_next_key_on_429_without_waiting`, `test_groq_waits_retry_after_when_all_keys_limited`, `test_groq_gives_up_after_max_rounds` |
| R5.3 | `llm.GroqClient`, `llm.KeyRotator` | `test_groq_disables_rejected_key_and_rotates_without_waiting`, `test_groq_fails_clearly_when_every_key_is_rejected` |
| R6.1 | `.gitignore`, `.pre-commit-config.yaml` | private-key hook in pre-commit |
| R6.2 | `.github/workflows/ci.yml`, `llm.FakeLLM` | whole suite |
