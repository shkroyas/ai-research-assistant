"""Run the research pipeline without the UI and save the brief to disk.

Example:
    research-brief "Analyze the food delivery market in Nepal" --provider groq --out samples
"""

import argparse
import json
import re
import sys
from pathlib import Path

from market_research import pipeline
from market_research.config import Settings
from market_research.llm import LLMError
from market_research.models import ResearchState
from market_research.render import brief_to_markdown

FILLER_WORDS = {
    "a",
    "an",
    "analyse",
    "analyze",
    "for",
    "in",
    "industry",
    "market",
    "of",
    "on",
    "research",
    "the",
}


def slugify(query: str, max_words: int = 6) -> str:
    """Turn a query into a short file name, e.g. 'food-delivery-nepal'."""
    words = re.findall(r"[a-z0-9]+", query.lower())
    kept = [w for w in words if w not in FILLER_WORDS] or words
    return "-".join(kept[:max_words]) or "research-brief"


def write_outputs(state: ResearchState, out_dir: Path, name: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{name}.md"
    json_path = out_dir / f"{name}.json"
    md_path.write_text(brief_to_markdown(state), encoding="utf-8")
    json_path.write_text(
        json.dumps(state.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    return md_path, json_path


def intake_message(state: ResearchState) -> str:
    """Explain why no brief was written, and what to try instead."""
    intake = state.intake
    if intake.status == "unclear":
        lines = ["The request needs clarifying before research."]
        if intake.question:
            lines.append(intake.question)
    else:
        lines = ["This request was declined."]
    if intake.reason:
        lines.append(f"Reason: {intake.reason}")
    if intake.suggestions:
        lines.append("Try instead:")
        lines += [f"  - {s}" for s in intake.suggestions]
    return "\n".join(lines)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="research-brief",
        description="Produce a sourced research brief for a market, company, comparison or topic.",
    )
    parser.add_argument("query", help='for example "Analyze the food delivery market in Nepal"')
    parser.add_argument(
        "--provider",
        choices=["bedrock", "groq"],
        help="model to use (default: the first entry of LLM_PROVIDERS)",
    )
    parser.add_argument("--out", type=Path, default=Path("samples"), help="output folder")
    parser.add_argument("--name", help="file name without extension (default: from the query)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        settings = Settings()
        orchestrator = pipeline.build_orchestrator(settings, args.provider)

        def on_step(agent: str, state: ResearchState) -> None:
            step = state.trace[-1]
            print(f"{step.agent}: {step.action}", file=sys.stderr)

        state = orchestrator.run(args.query, on_step=on_step)
    except (LLMError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not state.intake.proceed:
        print(intake_message(state), file=sys.stderr)
        return 2

    md_path, json_path = write_outputs(state, args.out, args.name or slugify(args.query))
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
