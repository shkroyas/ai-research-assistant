# 002 Release v1.0.0: tasks

Each task is one commit. Check a task off when its commit is on `main`.

- [x] **T1** Write this spec (requirements, design, tasks).
- [x] **T2** Add `market_research/cli.py`, the `research-brief` script and `make sample`, with offline tests for the slug, the written files and the error exit. *(R1.1 to R1.3)*
- [ ] **T3** Add `Dockerfile`, `.dockerignore` and `docker-compose.yml`. *(R2.1 to R2.5)*
- [ ] **T4** Add the `docker-build` CI job. *(R3.1, R3.2)*
- [ ] **T5** Add `CHANGELOG.md`, set the version to `1.0.0`, and update the README with sample, Docker and specs sections. *(R4.1 to R4.3)*
- [ ] **T6** Run the Nepal query live, commit `samples/food-delivery-nepal.md` and `.json` and a screenshot. *(R1.4)*
- [ ] **T7** Clone the repo fresh, follow only the README, then tag `v1.0.0`. *(R4.4)*

## How to do T6 (on a machine with keys)

```bash
make sample                                   # Claude on Bedrock, the default
# or
uv run research-brief "Analyze the food delivery market in Nepal" --provider groq --out samples
```

Read the brief before committing it. If the Critic did not approve it, or a claim looks wrong, adjust the prompts and run again.
