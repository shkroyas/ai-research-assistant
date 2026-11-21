"""Structured data passed between the agents.

Every handoff (Orchestrator -> Researcher -> Analyst -> Critic) reads and writes
these Pydantic models, so each step's input and output is validated.
"""

from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, computed_field, field_validator

MAX_COMPETITORS = 2

Evidence = Literal["scraped page", "search snippet", "sample data"]


def domain_of(url: str | None) -> str | None:
    """'https://www.example.com/a' -> 'example.com'."""
    if not url:
        return None
    host = urlsplit(url).hostname or ""
    return host.removeprefix("www.") or None


class Finding(BaseModel):
    """One piece of evidence gathered by the Researcher."""

    id: str = Field(pattern=r"^F\d+$", description="Citation id such as 'F1'.")
    claim: str = Field(min_length=1)
    source_title: str
    source_url: str | None = None
    is_sample_data: bool = False
    evidence: Evidence = "search snippet"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def domain(self) -> str | None:
        return domain_of(self.source_url)


class Competitor(BaseModel):
    """A competitor named in the brief, backed by at least one finding."""

    name: str = Field(min_length=1)
    note: str
    finding_ids: list[str] = Field(default_factory=list)


class Brief(BaseModel):
    """The research brief shown to the user."""

    summary: str = Field(min_length=1)
    competitors: list[Competitor] = Field(default_factory=list, max_length=MAX_COMPETITORS)
    observations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class Critique(BaseModel):
    """The Critic's verdict on a draft brief."""

    approved: bool
    issues: list[str] = Field(default_factory=list)
    revision_request: str | None = None


class StepLog(BaseModel):
    """One entry in the agent trace shown in the UI."""

    agent: str
    action: str
    detail: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: int | None = None


class QualityReport(BaseModel):
    """Evidence quality of a finished run, computed in code (see quality.py)."""

    findings: int
    cited: int
    citation_coverage: float = Field(ge=0, le=1)
    domains: list[str] = Field(default_factory=list)
    scraped_pages: int = 0
    search_snippets: int = 0
    sample_findings: int = 0
    grounding_problems: list[str] = Field(default_factory=list)


class ResearchState(BaseModel):
    """Shared state handed from agent to agent."""

    query: str
    findings: list[Finding] = Field(default_factory=list)
    draft: Brief | None = None
    critique: Critique | None = None
    revisions_used: int = 0
    trace: list[StepLog] = Field(default_factory=list)
    quality: QualityReport | None = None
    duration_ms: int | None = None

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be empty")
        return value

    @property
    def uses_sample_data(self) -> bool:
        return any(f.is_sample_data for f in self.findings)

    def log(self, agent: str, action: str, **detail: Any) -> None:
        self.trace.append(StepLog(agent=agent, action=action, detail=detail))
