# Changelog

All notable changes to this project are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- Fixes from the full audit (spec 011):
  - `.env.example` can be copied as it is: the Groq and Tavily placeholder keys are commented out, so the app stays in offline sample mode, and a blank key counts as unset.
  - Markdown bold (`**Foodmandu**`) is no longer mistaken for a masked figure, so evidence sentences with bold are kept and a brief that uses bold can be approved.
  - `LOG_LEVEL` is applied in the CLI and the app; the unused `get_settings()` is removed.
  - Search plans get today's date, so they ask for current data instead of 2023 or 2024.
  - The same article is one finding even with tracking parameters (`?fr=`, `utm_*`) or on a mirror site with identical text.
  - With no findings, the Quality tab warns instead of showing a green tick, the Analyst does not name companies that no finding names, and offline mode says which sample topics are bundled.
  - The scraper skips link lists ("Also, read: ...") and, in PDFs, abbreviation pages and over-long chunks.
  - The scraper's HTTP client is closed after each run and asks for PDFs when PDF reading is on.
  - Competitor notes no longer show the same citation twice.
  - Social media posts are left out when at least five other on-focus sources exist.

- User-facing text now says "market, company or topic" instead of "company or industry".

- Briefs drifted to the global market (global market size, DoorDash and Uber Eats for a Nepal query). The Researcher now names the focus of the query, adds it to every search, ranks on-focus results first and keeps at most three background results, labelled as such for the Analyst.
- Redacted figures such as `US$ ****** million in ****` and markdown table noise no longer reach the brief: they are removed from snippets and page passages, and code flags any that remain.

### Added

- Request types: the Researcher recognises market, company, comparison and topic requests, plans searches for each, and the Analyst and Critic adapt the brief to the type. Requests about the whole world have no focus (spec 006).
- Clarifying questions and declines: vague or ambiguous requests get one clarifying question with ready-to-run suggestions, and harmful or off-topic requests are declined with a reason, before any search (spec 007).
- Safety: failed searches are skipped, model calls time out, extra competitors and blank lines from the model are trimmed, the app shows a message instead of a traceback, the query box is limited to 400 characters, the scraper never fetches private or metadata addresses, and prompts treat sources as untrusted (spec 007).
- Optional PDF report reading: a "Read PDF reports" switch in the sidebar (`READ_PDFS`, off by default) reads the first 20 pages of PDFs up to 10 MB and keeps the most relevant passage (spec 008).
- Consistent runs: model calls use a low temperature (`LLM_TEMPERATURE`, default 0.2; dropped automatically for models that reject it), and the Analyst picks the competitors the most findings mention (spec 009).
- Fixes from live runs (spec 010): a single-company request is no longer treated as a comparison, a company is never its own competitor, topic requests focus on the industry they are about, page noise (table headers, icon text, emoji) is dropped, social media posts rank after articles, and declines give a clear reason.
- Grounding rule: a competitor supported only by background findings blocks approval.
- Focus coverage in the quality report, an "About <focus>" metric in the Quality tab, and an "On focus" column in the Evidence tab.
- Spec 005 with acceptance criteria and traceability.

## [1.0.0] - 2026-11-22

### Added

- Four agents (Orchestrator, Researcher, Analyst, Critic) that share one validated `ResearchState` and produce a brief with a summary, up to two competitors, key observations, sources and missing information.
- Evidence-first briefs: findings are numbered `F1..F10`, every observation must cite them, and invalid citations block approval in code.
- At most one Critic-requested revision, enforced in the Orchestrator and in settings.
- Live web search with Tavily, and a clearly labelled sample dataset when no key is set.
- Model picker: Claude on Amazon Bedrock (InvokeModel) or Groq.
- Groq key rotation: switch key on HTTP 429 and back off only when every key is limited; disable a key on HTTP 401 or 403.
- Streamlit UI with live agent steps, a summary bar, the brief, Markdown and JSON downloads, and an agent trace.
- `research-brief` command and `make sample` to save a brief without the UI.
- Dockerfile, docker-compose and `.dockerignore`.
- CI: lint, offline tests, and a Docker build with a container smoke test on every pull request.
- Specs with acceptance criteria and a traceability table in `specs/`.
- Page reading: the Researcher fetches result pages in parallel, respects `robots.txt`, and keeps the most relevant passage, falling back to the snippet. It can be switched off with `SCRAPE_PAGES`.
- Quality report computed in code (citation coverage, source domains, pages read, remaining citation problems), and timings for every agent step.
- Rebuilt Streamlit page:
  - landing view with a workflow diagram and one-click examples;
  - live progress bar and metric row;
  - Brief, Evidence, Quality, Agent trace and Export tabs, with citations linked to their sources;
  - sidebar controls and run history.

[Unreleased]: https://github.com/shkroyas/ai-research-assistant/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/shkroyas/ai-research-assistant/releases/tag/v1.0.0
