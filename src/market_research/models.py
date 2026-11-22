"""Structured data passed between the agents.

Every handoff (Orchestrator -> Researcher -> Analyst -> Critic) reads and writes
these Pydantic models, so each step's input and output is validated.
"""

from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, computed_field, field_validator

MAX_COMPETITORS = 2
MAX_LIST_ITEMS = 8

Evidence = Literal["scraped page", "search snippet", "sample data"]
# What the user asked about: an industry, one company, several companies, or a theme.
RequestKind = Literal["market", "company", "comparison", "topic"]
REQUEST_KINDS: tuple[str, ...] = ("market", "company", "comparison", "topic")
# Whether a request can be researched as asked, needs a clarifying question, or is declined.
IntakeStatus = Literal["research", "unclear", "decline"]
INTAKE_STATUSES: tuple[str, ...] = ("research", "unclear", "decline")


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
    on_focus: bool = True  # False for general background that does not mention the focus

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

    @field_validator("competitors", mode="before")
    @classmethod
    def keep_first_competitors(cls, value: object) -> object:
        """A model that names three competitors loses the extras instead of failing."""
        return value[:MAX_COMPETITORS] if isinstance(value, list) else value

    @field_validator("observations", "missing_information", mode="before")
    @classmethod
    def drop_blank_lines(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [v for v in value if not isinstance(v, str) or v.strip()][:MAX_LIST_ITEMS]


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
    on_focus: int = 0
    focus: list[str] = Field(default_factory=list)
    kind: RequestKind = "market"
    grounding_problems: list[str] = Field(default_factory=list)


class Intake(BaseModel):
    """The first check on a request, made before any search runs."""

    status: IntakeStatus = "research"
    reason: str = ""
    question: str | None = None  # what to ask the user when the request is unclear
    suggestions: list[str] = Field(default_factory=list)  # research-ready rewrites

    @property
    def proceed(self) -> bool:
        return self.status == "research"


class ResearchState(BaseModel):
    """Shared state handed from agent to agent."""

    query: str
    intake: Intake = Field(default_factory=Intake)
    kind: RequestKind = "market"
    focus: list[str] = Field(default_factory=list)
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
        value = " ".join("".join(c if c.isprintable() else " " for c in value).split())
        if not value:
            raise ValueError("query must not be empty")
        return value

    @property
    def uses_sample_data(self) -> bool:
        return any(f.is_sample_data for f in self.findings)

    def log(self, agent: str, action: str, **detail: Any) -> None:
        self.trace.append(StepLog(agent=agent, action=action, detail=detail))
