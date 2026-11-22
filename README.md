# AI Research Assistant

A multi-agent market research app. Type a company or an industry, for example *"Analyze the food delivery market in Nepal"*, and four agents work in sequence to produce a short, sourced research brief:

| Agent | Job |
| --- | --- |
| **Orchestrator** | Receives the query, runs the workflow, enforces the one-revision limit |
| **Researcher** | Searches the web (Tavily) or, without a key, uses clearly labelled sample data |
| **Analyst** | Writes the brief using only the numbered findings, citing each claim as `[F1]`, `[F2]` |
| **Critic** | Checks evidence and coverage, approves or requests at most one revision |

The brief contains a **summary**, **up to two competitors**, **key observations**, and **sources plus missing information**.

**Author:** Royas Shakya ([@shkroyas](https://github.com/shkroyas))

---

## Contents

- [How it works](#how-it-works)
- [What you need](#what-you-need)
- [Run it locally](#run-it-locally)
- [Run with Docker](#run-with-docker)
- [Sample output](#sample-output)
- [Configuration](#configuration)
- [Setting up Amazon Bedrock](#setting-up-amazon-bedrock)
- [Tests and code quality](#tests-and-code-quality)
- [Project structure](#project-structure)
- [Design decisions](#design-decisions)
- [Specs](#specs)
- [Limitations](#limitations)

---

## How it works

```mermaid
flowchart LR
    UI[Streamlit UI] --> O[Orchestrator]
    O --> R[Researcher]
    R --> A[Analyst]
    A --> C{Critic}
    C -- approved --> B[Final brief + agent trace]
    C -- "revision request (max 1)" --> A
    R -. Tavily or sample data .- S[(Search)]
    R -. robots.txt-aware .- P[(Source pages)]
```

Every handoff passes a single Pydantic object, `ResearchState`, holding the query, findings, draft brief, critique and an agent trace. Each agent validates what it receives and what the model returns, so malformed output is caught at the boundary instead of reaching the user.

**Reads the sources, not just the snippets.** After searching, the Researcher fetches each result page in parallel. It checks `robots.txt` first, uses a timeout and a size limit, strips navigation and other boilerplate, and keeps the passage most relevant to the query. If a page cannot be read, the search snippet is kept and the reason is shown in the app.

**Understands the request first.** The Researcher reads the request before searching. It works out whether it is about a **market** (e.g. food delivery in Nepal), a **company** (Tesla), a **comparison** (eSewa vs Khalti) or a **topic** (AI adoption in banking), and plans different searches for each. If a request is too vague (e.g. "the best company") or ambiguous (e.g. "Mercury"), it asks one clarifying question and offers ready-to-run suggestions instead of guessing. Requests that are harmful or not business research are declined with a reason. Obvious cases are caught by code rules without a model call.

**Stays on the market you asked about.** The Researcher first names the query's focus (for example *Nepal*, with local names such as *Kathmandu*), makes every search include it, and ranks results that mention it first. At most three general results are kept, marked as background, so a brief about Nepal is not built on global figures or on DoorDash and Uber Eats. Redacted figures such as `US$ ****` and table noise are removed from the evidence before the Analyst sees it.

**Evidence first.** The Researcher numbers every finding (`F1`, `F2`, ...). The Analyst may only cite those ids. Plain code (`grounding.py`) then flags uncited observations, invented citations competitors with no supporting finding, competitors backed only by background findings, and masked figures, and the Critic sees those flags.

**Quality you can see.** Each run ends with a quality report computed in code: citation coverage, how many findings are about the focus, distinct source domains, how many findings came from full pages, and any remaining citation problems. Every agent step is timed.

**Choose your model.** A picker in the sidebar switches between **Claude on Amazon Bedrock** and **Groq**. Groq appears only when at least one Groq key is configured.

**Key rotation for Groq.** Several Groq keys can be configured. On HTTP 429 (too many requests) the client switches to the next key at once, and only when every key is rate limited does it wait with back-off, honouring `retry-after`. On HTTP 401 or 403 (invalid or forbidden key) that key is disabled for the session and the next key is used, with no waiting.

---

## What you need

| Requirement | Needed? | Where to get it |
| --- | --- | --- |
| Python 3.11 or newer | Yes | [python.org](https://www.python.org/downloads/) |
| A model provider: AWS Bedrock (Claude) and/or Groq | At least one | See below |
| AWS account with Bedrock access to Claude | For Claude | [AWS console](https://console.aws.amazon.com/bedrock/) |
| Groq API key(s) | For Groq, free tier | [console.groq.com/keys](https://console.groq.com/keys) |
| Tavily API key | Optional, for live web search | [app.tavily.com](https://app.tavily.com) (free tier) |
| [uv](https://docs.astral.sh/uv/) | Optional, faster installs | `pip install uv` |

No GPU is required. All model calls go to hosted APIs.

Without a Tavily key the Researcher falls back to a small, clearly labelled sample dataset, so the app still runs end to end.

---

## Run it locally

```bash
# 1. Clone
git clone https://github.com/shkroyas/ai-research-assistant.git
cd ai-research-assistant

# 2. Configure
cp .env.example .env
#    then edit .env and add your keys (see Configuration)

# 3a. Install and run with uv (recommended)
uv sync
uv run streamlit run app/streamlit_app.py

# 3b. Or with plain pip
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
streamlit run app/streamlit_app.py
```

Open http://localhost:8501, pick a model in the sidebar, type a company or industry (or click an example), and click **Run research**.

The results page has a metric row (findings, sources, citation coverage, Critic verdict, run time) and five tabs:

| Tab | Shows |
| --- | --- |
| **Brief** | Summary, up to two competitors, key observations, sources and missing information. Each `F#` citation links to its source. |
| **Evidence** | Every finding passed to the Analyst, with its domain, whether it came from the full page or a snippet, and whether the brief cites it |
| **Quality** | The quality report and the Critic's review |
| **Agent trace** | Every handoff between agents, in order, with durations |
| **Export** | The brief as Markdown and the full run as JSON |

The sidebar also lets you switch page reading on or off, set the search depth, and reopen earlier runs from the same session.

To get a brief without the UI:

```bash
uv run research-brief "Analyze the food delivery market in Nepal" --provider groq --out samples
```

This writes `samples/food-delivery-nepal.md` and `samples/food-delivery-nepal.json`. `--provider` is `bedrock` or `groq`, and defaults to the first entry of `LLM_PROVIDERS`.

---

## Run with Docker

```bash
cp .env.example .env      # then add your keys
docker compose up --build
```

Open http://localhost:8501. Compose reads `.env` and mounts `~/.aws` read-only, so an `AWS_PROFILE` set in `.env` works inside the container without copying keys into it.

Without Compose:

```bash
docker build -t ai-research-assistant .
docker run --rm -p 8501:8501 --env-file .env ai-research-assistant
```

The image installs only runtime dependencies from `uv.lock`, runs as a non-root user, and contains no `.env`, tests or git history.

---

## Sample output

[`samples/food-delivery-nepal.md`](samples/food-delivery-nepal.md) is a brief from a live run of *"Analyze the food delivery market in Nepal"*. [`samples/food-delivery-nepal.json`](samples/food-delivery-nepal.json) is the full run behind it: findings, drafts, critique and the agent trace. To make your own, run `make sample`.

---

## Configuration

All settings are environment variables, read from `.env`. See [`.env.example`](.env.example) for the full list.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDERS` | `bedrock,groq` | Models offered in the picker; the first is selected by default |
| `AWS_REGION` | `us-east-1` | Region where Bedrock model access is enabled |
| `AWS_PROFILE` | unset | Named AWS CLI profile, if you use one |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-opus-4-6-v1` | Claude inference profile id on Bedrock, copied from the console |
| `BEDROCK_API` | `invoke` | `invoke` (InvokeModel, works with Claude Opus 4.6) or `mantle` (Claude 4.7 and later) |
| `GROQ_API_KEYS` | unset | One or more Groq keys, comma separated |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq chat model. Groq retires models over time; list the ones your key can use at `https://api.groq.com/openai/v1/models` |
| `TAVILY_API_KEY` | unset | Enables live web search |
| `MAX_SEARCH_RESULTS` | `5` | Results per search query |
| `SCRAPE_PAGES` | `true` | Read each result page and keep its most relevant passage |
| `MAX_REVISIONS` | `1` | Critic revision limit (0 or 1) |

Only using Groq? Set `LLM_PROVIDERS=groq`. Only Claude? Set `LLM_PROVIDERS=bedrock`.

`.env` is git-ignored. Never commit real keys.

---

## Setting up Amazon Bedrock

1. In the AWS console, open **Amazon Bedrock → Model access** in your chosen region and enable the Claude model you want to use.
2. Create an IAM user or role with permission to invoke Bedrock models (for example the `AmazonBedrockLimitedAccess` managed policy, or a policy allowing `bedrock:InvokeModel` on that model).
3. Give the app credentials using any standard AWS method:
   - `aws configure` (writes `~/.aws/credentials`), then optionally set `AWS_PROFILE`, or
   - set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env`.
4. Set `AWS_REGION` and `BEDROCK_MODEL_ID` in `.env` to match what you enabled. Claude Opus 4.6 cannot be called by its plain model id (on-demand throughput is not supported), so use its **inference profile** id, which starts with `us.` or `global.`. List the ids available to you with `aws bedrock list-inference-profiles --region us-east-1`.
5. Keep `BEDROCK_API=invoke` for Claude Opus 4.6. Claude 4.7 and later models can also use `BEDROCK_API=mantle`.

> The project pins the `anthropic` SDK to 1.x. SDK 2.x sends a newer API version that Bedrock accepts only for Claude 4.7 and later, so 1.x keeps Claude Opus 4.6 working.

---

## Tests and code quality

The test suite runs fully offline: a `FakeLLM` returns scripted responses and search uses sample data, so no API keys or network are needed.

```bash
make test     # pytest with coverage
make lint     # ruff lint and format check
make format   # auto-fix lint issues and format
```

GitHub Actions runs two jobs on every pull request and on every push to `main`: lint plus the full test suite, and a Docker build with a container smoke test.

---

**Fails safely.** A failed search is skipped and noted in the trace, model calls time out, model output that breaks a limit is trimmed rather than fatal, and the app shows a short message instead of a traceback. Source pages are untrusted: the scraper never fetches private or cloud metadata addresses (also through redirects), and the agents are told to ignore instructions found inside sources.

## Project structure

```text
ai-research-assistant/
├── app/
│   ├── streamlit_app.py          # page flow: sidebar, query, results or landing view
│   └── ui/                       # components (tabs, metrics, tables) and text helpers
├── .streamlit/config.toml        # theme
├── src/market_research/
│   ├── config.py                 # settings from environment variables
│   ├── models.py                 # Pydantic contracts passed between agents
│   ├── llm.py                    # Bedrock Claude, Groq with key rotation, FakeLLM
│   ├── search.py                 # Tavily search and labelled sample data
│   ├── intake.py                 # rules for requests that cannot be researched as asked
│   ├── evidence.py               # evidence cleaning, focus matching and ranking
│   ├── scraper.py                # robots.txt-aware page reading and passage choice
│   ├── quality.py                # citation coverage and other evidence metrics
│   ├── grounding.py              # citation checks in plain code
│   ├── cli.py                    # research-brief command
│   └── agents/                   # orchestrator, researcher, analyst, critic
├── data/sample/                  # labelled sample data for offline demos
├── samples/                      # example output brief
├── specs/                        # requirements, design and tasks per feature
├── tests/                        # offline unit and integration tests
├── .github/workflows/ci.yml      # lint, tests and Docker build on every PR
├── Dockerfile, docker-compose.yml
├── .env.example                  # configuration template, no secrets
└── pyproject.toml
```

---

## Design decisions

- **No agent framework.** Four small agent classes and an orchestrator loop are easier to read, test and debug than a framework for a fixed four-step pipeline. Each agent shares the same `run(state) -> state` interface, so a framework such as LangGraph could be introduced later without rewriting the agents.
- **Code checks what code can.** The revision limit, the two-competitor cap and citation validity are enforced in Python, not left to the model.
- **Honest data labelling.** Sample data is marked in the data model, in the UI and in the exported brief. Missing information is listed rather than guessed.
- **Polite, bounded scraping.** Pages are fetched only from search results, never crawled. `robots.txt` is respected, requests identify the app, and every fetch has a timeout and a size limit. Static HTML parsing (BeautifulSoup) keeps the image small; a headless browser was rejected as too heavy for the benefit.
- **Ask rather than guess, but only when needed.** Whether a request is clear is decided in the same model call that plans the searches, so clear requests cost nothing extra. The prompt prefers answering whenever one sensible reading exists.
- **Provider independence.** Agents depend only on a one-method `LLMClient` interface, so new providers can be added without touching the agents.

---

## Specs

Work is planned in [`specs/`](specs/README.md) before it is built. Each spec lists numbered acceptance criteria, the design and the task list. [Spec 001](specs/001-research-brief/requirements.md) maps every requirement of the assignment to the code and the test that proves it.

---

## Limitations

- Brief quality depends on what web search returns; niche or very local topics may have thin coverage, which the brief reports under *Missing information*.
- The sample dataset is small and illustrative, intended only for offline demos.
- Page reading does not run JavaScript, so content rendered only in the browser falls back to the search snippet. Paywalled pages are not read.
- Briefs are drafts for a person to review, not verified research.

---

## License

[MIT](LICENSE) © 2026 Royas Shakya
