# 002 Release v1.0.0: requirements

**Status:** In progress.

## Goal

Make the project ready to submit and easy for a reviewer to run: a real sample output in the repo, a container that runs the same way on any machine, and a tagged release.

## Acceptance criteria

### R1 Sample output

- **R1.1** One command runs the full pipeline without the UI and writes the brief as Markdown and the full run as JSON.
- **R1.2** The command takes the query, the model (`bedrock` or `groq`) and an output folder. File names are derived from the query, for example `food-delivery-nepal.md`.
- **R1.3** The command exits with a non-zero status and a clear message when the model fails or no provider is configured, and writes no partial files.
- **R1.4** The repository contains one sample output from a live run, `samples/food-delivery-nepal.md` and `.json`, linked from the README.

### R2 Container

- **R2.1** `docker build .` produces an image that starts the Streamlit app on port 8501.
- **R2.2** The image installs only runtime dependencies from the lock file and runs as a non-root user.
- **R2.3** The image contains no `.env`, keys, tests or git history.
- **R2.4** `docker compose up` starts the app with settings read from `.env`, and can reuse local AWS credentials read-only.
- **R2.5** The container reports health through Streamlit's health endpoint.

### R3 Continuous integration

- **R3.1** CI builds the Docker image on every pull request, so a broken Dockerfile fails the check.
- **R3.2** The existing offline lint and test job keeps running unchanged.

### R4 Release

- **R4.1** `CHANGELOG.md` records what v1.0.0 contains.
- **R4.2** The package version is `1.0.0`.
- **R4.3** The README explains the sample command, Docker usage and where to find the specs.
- **R4.4** A fresh clone, following only the README, runs the app.

## Out of scope

- Cloud deployment, which is spec 003.
- Any change to agent behaviour or prompts, unless the live run shows a defect.
