# 002 Release v1.0.0: design

## Sample command (R1)

A small module, `market_research/cli.py`, reuses `pipeline.build_orchestrator` and `render.brief_to_markdown`, so the sample is produced by exactly the same code path as the UI.

```text
research-brief "Analyze the food delivery market in Nepal" --provider groq --out samples
```

- Exposed as the `research-brief` console script and as `make sample`.
- The file name comes from a slug of the query with filler words removed ("analyze", "the", "market", "in"), so the example becomes `food-delivery-nepal`. `--name` overrides it.
- Progress lines go to stderr and file paths to stdout, so the command can be scripted.
- Both files are written only after the run succeeds (R1.3). `LLMError` and configuration errors map to exit code 1 with a one-line message.

**Rejected:** a separate script under `scripts/`. A console script is installed with the package, is testable as a normal function, and works the same inside the container.

## Container (R2)

```text
python:3.12-slim
  └─ uv (copied from the official uv image, pinned)
  └─ uv sync --frozen --no-dev       # dependency layer, cached unless uv.lock changes
  └─ copy src, app, data              # app layer
  └─ user "app", port 8501, HEALTHCHECK /_stcore/health
```

- Two `uv sync` steps: dependencies first (cached), then the project itself. This keeps rebuilds fast when only code changes.
- The Streamlit server is bound to `0.0.0.0` with headless mode and usage stats off.
- `.dockerignore` excludes `.env*` (except `.env.example`), `.git`, tests, caches and `samples/`.
- `docker-compose.yml` reads `.env` through `env_file` and mounts `~/.aws` read-only, so a local `AWS_PROFILE` works inside the container without copying keys.

**Rejected:** a multi-stage build. With `uv` and a slim base the single stage is small enough, and it is easier to read.

## CI (R3)

A second job, `docker-build`, runs `docker/build-push-action` with `push: false` and the GitHub Actions cache. It runs in parallel with `lint-and-test`, so total CI time barely changes.

## Release (R4)

- `CHANGELOG.md` follows the Keep a Changelog layout.
- The version in `pyproject.toml` moves to `1.0.0` and `uv.lock` is refreshed.
- The tag `v1.0.0` is created on `main` after the release pull request merges.
