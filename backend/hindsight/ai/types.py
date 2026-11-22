"""Inputs and outputs of the auditor. The output models double as Gemini response schemas,
so they avoid defaults and unions that structured output can't express."""

from enum import StrEnum

from pydantic import BaseModel, Field


class Category(StrEnum):
    TIME = "time"  # durations, schedules, free time
    SELF = "self"  # own skill, discipline, motivation, habits
    PEOPLE = "people"  # what other people will do
    MONEY = "money"  # costs, income, value for money
    EXTERNAL = "external"  # tools, markets, institutions, anything else outside your control
    OTHER = "other"


class Risk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Verdict(StrEnum):
    HELD = "held"
    FAILED = "failed"
    UNCLEAR = "unclear"


# ── inputs ──────────────────────────────────────────────────────────────────────


class DecisionInput(BaseModel):
    title: str
    reasoning: str
    alternatives: str | None = None
    expected_outcome: str
    confidence: float
    domain: str
    review_at: str | None = None  # ISO date, used to phrase the pre-mortem


class PastCase(BaseModel):
    decision_id: int
    title: str
    happened: bool
    failed_assumptions: list[str]
    similarity: float


class AssumptionToJudge(BaseModel):
    id: int
    text: str
    category: Category


# ── outputs ─────────────────────────────────────────────────────────────────────


class ExtractedAssumption(BaseModel):
    text: str = Field(
        description="One short first-person sentence, e.g. 'I'll have free evenings'."
    )
    category: Category
    risk: Risk


class RepeatWarning(BaseModel):
    assumption: str = Field(description="The current assumption that repeats a past failure.")
    past_decision_id: int = Field(description="The id of the past decision where it failed.")
    note: str = Field(description="One sentence on what happened last time.")


class AuditResult(BaseModel):
    assumptions: list[ExtractedAssumption]
    missing_considerations: list[str]
    premortem: str
    repeat_warnings: list[RepeatWarning]


class AssumptionVerdict(BaseModel):
    assumption_id: int
    verdict: Verdict
    evidence: str = Field(
        description="Exact words copied from the outcome notes that support the verdict; "
        "empty string when the verdict is unclear."
    )


class ReviewResult(BaseModel):
    verdicts: list[AssumptionVerdict]
    lesson: str
