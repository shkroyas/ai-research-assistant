# 009 Consistent runs: requirements

Status: done

## Why

Running the same request twice named different competitors. Three things vary between runs: the model's wording of the search queries, the live search results, and which two competitors the Analyst picks. The first and last can be made much steadier without making the brief rigid.

## Acceptance criteria

- **R1** Every model call uses a low temperature, `LLM_TEMPERATURE`, default `0.2` (0 to 1). It is deliberately not zero, so wording can still vary slightly.
- **R2** If a model rejects the temperature setting (newer Claude models do), the client drops it for the session and retries once, so a run never fails because of it.
- **R3** When more than two competitors qualify, the Analyst picks the ones the most findings mention, then the largest by the evidence.
- **R4** Live search results still change over time; the README says so.

## Traceability

| Criterion | Code | Tests |
| --- | --- | --- |
| R1 | `config.llm_temperature`, `llm.build_llm`, `BedrockClaudeClient`, `GroqClient` | `test_bedrock_sends_the_configured_temperature`, `test_groq_sends_the_configured_temperature`, `test_temperature_defaults_low_but_not_zero_and_is_validated` |
| R2 | `BedrockClaudeClient.complete` | `test_models_that_reject_temperature_fall_back_to_their_default` |
| R3 | `prompts.ANALYST_SYSTEM` | `test_analyst_picks_competitors_by_how_often_the_findings_mention_them` |
| R4 | `README.md` (Limitations) | - |

## Tasks

- [x] **T1** Temperature setting and client support with fallback.
- [x] **T2** Stable competitor choice in the Analyst prompt.
- [x] **T3** Live check: the Nepal request named the same two competitors in 5 of 6 runs. Claude on Bedrock rejects the temperature setting, so on Claude the competitor rule does this work (spec 010).
