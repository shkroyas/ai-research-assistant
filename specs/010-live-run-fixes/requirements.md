# 010 Fixes from the live runs: requirements

Status: done

## Why

Specs 005 to 009 were checked live on Claude (Bedrock) and Groq with six requests. Markets, comparisons, clarifying questions and declines worked on both. These problems remained:

1. **Groq read "Research Tesla and its main competitors" as a comparison** and put Tesla's rivals in the focus. Its brief named competitors with the note "focus company" and was not approved.
2. **Topic focus was too thin.** "AI adoption in banking" got the focus `["AI"]`, so every source counted as on focus.
3. **Claude on Bedrock rejects the temperature setting.** The fallback worked, but every run paid for one rejected call and logged a warning.
4. **Page noise reached the evidence**, for example a table header ("Rank Company Details Short Description Total Funding...") and icon text ("arrow_forward 🍔🍟"). Facebook and Instagram posts were cited ahead of articles.
5. **Groq's decline reason was vague** ("I'm sorry, but I can't fulfill that request.").

## Acceptance criteria

- **R1** For company and comparison requests, the focus keeps only the companies the user named. A "comparison" that names one company and has no "vs" or "compare" becomes a company request.
- **R2** A company cannot be listed as its own competitor; code flags it and blocks approval. Competitor notes describe the competitor.
- **R3** For topic requests, the focus is the industry, place or company the topic is about, with its word forms (e.g. banking, banks, bank).
- **R4** A Bedrock model that rejects temperature is remembered for the rest of the process, and the message is logged at info level.
- **R5** Icon words and emoji are removed from evidence, text that does not read as prose is dropped, and social media posts rank after other on-focus sources.
- **R6** A declined request gets a one-sentence reason that says why.

## Traceability

| Criterion | Code | Tests |
| --- | --- | --- |
| R1 | `evidence.settle_kind`, `Researcher.plan`, `prompts.RESEARCHER_SYSTEM` | `test_single_company_request_is_not_a_comparison`, `test_other_requests_keep_their_type_and_focus`, `test_researcher_applies_the_correction` |
| R2 | `grounding.check_grounding`, `prompts.ANALYST_SYSTEM` | `test_company_cannot_be_its_own_competitor` |
| R3, R6 | `prompts.RESEARCHER_SYSTEM` | `test_prompt_keeps_rivals_out_of_the_focus_and_asks_for_a_clear_decline_reason` |
| R4 | `BedrockClaudeClient` | `test_models_that_reject_temperature_fall_back_to_their_default` |
| R5 | `evidence.clean_evidence`, `evidence.looks_like_prose`, `evidence.rank_results` | `test_page_noise_is_removed`, `test_social_posts_rank_after_other_sources` |

## Tasks

- [x] **T1** Fixes and tests for R1 to R6.
- [ ] **T2** Re-run "Research Tesla and its main competitors" and "AI adoption in banking" on Groq.
