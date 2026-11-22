"""API request/response models."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

Domain = Literal["career", "study", "projects", "health", "money", "relationships", "other"]
Status = Literal["open", "due", "reviewed"]
DOMAINS: tuple[str, ...] = get_args(Domain)


class _Input(BaseModel):
    # extra="forbid": unknown fields such as created_at are rejected with a 422, not silently
    # dropped. Clients can't backdate a decision.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DecisionCreate(_Input):
    title: str = Field(min_length=3, max_length=200)
    reasoning: str = Field(min_length=20, max_length=5000)
    alternatives: str | None = Field(default=None, max_length=2000)
    expected_outcome: str = Field(min_length=3, max_length=1000)
    confidence: float = Field(ge=0.5, le=0.99, description="P(expected outcome happens)")
    domain: Domain = "other"
    review_at: date

    @field_validator("alternatives")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("review_at")
    @classmethod
    def _review_window(cls, value: date) -> date:
        today = date.today()
        if value < today - timedelta(days=1):  # one day of slack for time zones
            raise ValueError("review date can't be in the past")
        if value > today + timedelta(days=730):
            raise ValueError("review date must be within two years")
        return value


class OutcomeCreate(_Input):
    happened: bool = Field(description="Did the expected outcome happen?")
    what_happened: str = Field(min_length=10, max_length=5000)


class AssumptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    category: str
    risk: str
    verdict: str | None
    evidence: str | None
    evidence_grounded: bool | None


class OutcomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    happened: bool
    what_happened: str
    lesson: str | None
    review_status: str
    review_error: str | None
    created_at: datetime


class SimilarOut(BaseModel):
    id: int
    title: str
    similarity: float
    happened: bool
    failed_assumptions: list[str]


class RepeatWarningOut(BaseModel):
    assumption: str
    past_decision_id: int
    note: str


class DecisionSummary(BaseModel):
    id: int
    title: str
    domain: str
    confidence: float
    created_at: datetime
    review_at: date
    status: Status
    audit_status: str
    happened: bool | None
    assumption_count: int
    failed_count: int


class DecisionDetail(DecisionSummary):
    reasoning: str
    alternatives: str | None
    expected_outcome: str
    premortem: str | None
    missing_considerations: list[str]
    repeat_warnings: list[RepeatWarningOut]
    audit_error: str | None
    audit_provider: str | None
    assumptions: list[AssumptionOut]
    outcome: OutcomeOut | None
    similar: list[SimilarOut]
    brier: float | None = Field(description="(confidence - outcome)^2 once reviewed")


# ── insights ───────────────────────────────────────────────────────────────────


class CalibrationBin(BaseModel):
    lo: float
    hi: float
    n: int
    mean_confidence: float | None
    hit_rate: float | None


class CalibrationGroup(BaseModel):
    n: int
    brier: float | None
    hit_rate: float
    mean_confidence: float


class TrendPoint(CalibrationGroup):
    month: str


class DomainCalibration(CalibrationGroup):
    domain: str


class Calibration(BaseModel):
    n: int
    brier: float | None
    skill_score: float | None
    base_rate: float | None
    mean_confidence: float | None
    overconfidence: float | None
    bins: list[CalibrationBin]
    trend: list[TrendPoint]
    by_domain: list[DomainCalibration]
    small_sample: bool


class PatternExample(BaseModel):
    decision_id: int
    decision_title: str
    text: str


class Pattern(BaseModel):
    category: str
    failed: int
    held: int
    unclear: int
    judged: int
    failure_rate: float | None
    lower_bound: float
    examples: list[PatternExample]


class Patterns(BaseModel):
    patterns: list[Pattern]
    emerging: list[Pattern]
    min_judged: int


class Counts(BaseModel):
    total: int
    open: int
    due: int
    reviewed: int


class Insights(BaseModel):
    counts: Counts
    calibration: Calibration
    patterns: Patterns


# ── system ─────────────────────────────────────────────────────────────────────


class Health(BaseModel):
    status: Literal["ok"]
    version: str
    provider: str
    model: str
    embed_model: str
    offline: bool


class TraceCall(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    workspace: str | None
    decision_id: int | None
    operation: str
    provider: str
    model: str
    model_version: str | None
    latency_ms: int
    attempts: int
    input_tokens: int | None
    output_tokens: int | None
    ok: bool
    error: str | None


class OperationStats(BaseModel):
    operation: str
    provider: str
    calls: int
    errors: int
    p50_ms: int | None
    p95_ms: int | None
    input_tokens: int
    output_tokens: int


class Traces(BaseModel):
    total_calls: int
    error_rate: float | None
    by_operation: list[OperationStats]
    calls: list[TraceCall]
