"""ORM models. Decisions are append-only: there is no update path for the reasoning fields."""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UTCDateTime, utcnow


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(200))
    reasoning: Mapped[str] = mapped_column(Text)
    alternatives: Mapped[str | None] = mapped_column(Text)
    expected_outcome: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    domain: Mapped[str] = mapped_column(String(32))
    review_at: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)

    audit_status: Mapped[str] = mapped_column(String(16), default="pending")
    audit_error: Mapped[str | None] = mapped_column(Text)
    audit_provider: Mapped[str | None] = mapped_column(String(80))
    premortem: Mapped[str | None] = mapped_column(Text)
    missing_considerations: Mapped[list[str]] = mapped_column(JSON, default=list)
    repeat_warnings: Mapped[list[dict]] = mapped_column(JSON, default=list)

    embedding: Mapped[bytes | None] = mapped_column(LargeBinary)
    embedding_model: Mapped[str | None] = mapped_column(String(80))
    # Only set on seeded demo rows: the theme cluster used as ground truth by the retrieval eval.
    theme: Mapped[str | None] = mapped_column(String(64))

    assumptions: Mapped[list["Assumption"]] = relationship(
        back_populates="decision",
        cascade="all, delete-orphan",
        order_by="Assumption.position",
    )
    outcome: Mapped["Outcome | None"] = relationship(
        back_populates="decision", cascade="all, delete-orphan", uselist=False
    )


class Assumption(Base):
    __tablename__ = "assumptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(16))
    risk: Mapped[str] = mapped_column(String(8))
    verdict: Mapped[str | None] = mapped_column(String(8))
    evidence: Mapped[str | None] = mapped_column(Text)
    evidence_grounded: Mapped[bool | None] = mapped_column(Boolean)

    decision: Mapped[Decision] = relationship(back_populates="assumptions")


class Outcome(Base):
    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), unique=True
    )
    happened: Mapped[bool] = mapped_column(Boolean)
    what_happened: Mapped[str] = mapped_column(Text)
    lesson: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(16), default="pending")
    review_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    decision: Mapped[Decision] = relationship(back_populates="outcome")


class LLMCall(Base):
    """One row per logical model call (retries are folded into `attempts`)."""

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    workspace: Mapped[str | None] = mapped_column(String(32))
    decision_id: Mapped[int | None] = mapped_column(
        Integer, index=True
    )  # no FK: traces outlive rows
    operation: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(80))
    model_version: Mapped[str | None] = mapped_column(String(80))
    latency_ms: Mapped[int] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    ok: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Text)
