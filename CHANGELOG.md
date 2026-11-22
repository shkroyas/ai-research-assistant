# Changelog

All notable changes to this project are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- Briefs drifted to the global market (global market size, DoorDash and Uber Eats for a Nepal query). The Researcher now names the focus of the query, adds it to every search, ranks on-focus results first and keeps at most three background results, labelled as such for the Analyst.
- Redacted figures such as `US$ ****** million in ****` and markdown table noise no longer reach the brief: they are removed from snippets and page passages, and code flags any that remain.

### Added

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
