# Changelog

All notable changes to this project are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

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

[1.0.0]: https://github.com/shkroyas/ai-research-assistant/releases/tag/v1.0.0
