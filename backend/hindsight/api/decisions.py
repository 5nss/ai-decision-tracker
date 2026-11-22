"""Decision endpoints. There is deliberately no PATCH: logged reasoning is immutable."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..ai import Auditor
from ..deps import AuditorDep, DbDep, WorkspaceDep
from ..models import Decision, Outcome
from ..schemas import (
    AssumptionOut,
    DecisionCreate,
    DecisionDetail,
    DecisionSummary,
    Domain,
    OutcomeCreate,
    OutcomeOut,
    RepeatWarningOut,
    SimilarOut,
    Status,
)
from ..services.audit import SIMILAR_K, run_audit
from ..services.retrieval import similar_reviewed
from ..services.review import run_review
from ..tracing import TraceBuffer

router = APIRouter(prefix="/decisions", tags=["decisions"])


def decision_status(d: Decision, today: date) -> Status:
    if d.outcome is not None:
        return "reviewed"
    return "due" if d.review_at <= today else "open"


def to_summary(d: Decision, today: date) -> DecisionSummary:
    return DecisionSummary(
        id=d.id,
        title=d.title,
        domain=d.domain,
        confidence=d.confidence,
        created_at=d.created_at,
        review_at=d.review_at,
        status=decision_status(d, today),
        audit_status=d.audit_status,
        happened=d.outcome.happened if d.outcome else None,
        assumption_count=len(d.assumptions),
        failed_count=sum(a.verdict == "failed" for a in d.assumptions),
    )


def to_detail(db: Session, d: Decision, auditor: Auditor) -> DecisionDetail:
    similar: list[SimilarOut] = []
    if d.embedding_model == auditor.embed_model:
        for past, score in similar_reviewed(db, d, SIMILAR_K, auditor.similarity_threshold):
            similar.append(
                SimilarOut(
                    id=past.id,
                    title=past.title,
                    similarity=round(score, 3),
                    happened=past.outcome.happened,
                    failed_assumptions=[a.text for a in past.assumptions if a.verdict == "failed"],
                )
            )
    summary = to_summary(d, date.today())
    return DecisionDetail(
        **summary.model_dump(),
        reasoning=d.reasoning,
        alternatives=d.alternatives,
        expected_outcome=d.expected_outcome,
        premortem=d.premortem,
        missing_considerations=d.missing_considerations or [],
        repeat_warnings=[RepeatWarningOut(**w) for w in (d.repeat_warnings or [])],
        audit_error=d.audit_error,
        audit_provider=d.audit_provider,
        assumptions=[AssumptionOut.model_validate(a) for a in d.assumptions],
        outcome=OutcomeOut.model_validate(d.outcome) if d.outcome else None,
        similar=similar,
        brier=(d.confidence - float(d.outcome.happened)) ** 2 if d.outcome else None,
    )


def get_decision_or_404(db: Session, workspace: str, decision_id: int) -> Decision:
    decision = db.scalars(
        select(Decision)
        .where(Decision.id == decision_id, Decision.workspace == workspace)
        .options(selectinload(Decision.assumptions), selectinload(Decision.outcome))
    ).first()
    if decision is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Decision not found")
    return decision


@router.get("", response_model=list[DecisionSummary])
def list_decisions(
    db: DbDep,
    workspace: WorkspaceDep,
    status_filter: Status | None = Query(default=None, alias="status"),
    domain: Domain | None = None,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[DecisionSummary]:
    stmt = (
        select(Decision)
        .where(Decision.workspace == workspace)
        .options(selectinload(Decision.assumptions), selectinload(Decision.outcome))
        .order_by(Decision.created_at.desc())
    )
    if domain:
        stmt = stmt.where(Decision.domain == domain)
    if q:
        stmt = stmt.where(Decision.title.ilike(f"%{q}%"))
    today = date.today()
    summaries = [to_summary(d, today) for d in db.scalars(stmt).all()]
    if status_filter:
        summaries = [s for s in summaries if s.status == status_filter]
    return summaries[:limit]


@router.post("", response_model=DecisionDetail, status_code=status.HTTP_201_CREATED)
def create_decision(
    body: DecisionCreate, db: DbDep, workspace: WorkspaceDep, auditor: AuditorDep
) -> DecisionDetail:
    decision = Decision(workspace=workspace, **body.model_dump())
    db.add(decision)
    db.commit()  # the decision is safe before any model call happens

    traces = TraceBuffer(workspace, decision.id)
    try:
        run_audit(db, decision, auditor, traces)
    finally:
        traces.flush(db)
    return to_detail(db, decision, auditor)


@router.get("/{decision_id}", response_model=DecisionDetail)
def get_decision(
    decision_id: int, db: DbDep, workspace: WorkspaceDep, auditor: AuditorDep
) -> DecisionDetail:
    return to_detail(db, get_decision_or_404(db, workspace, decision_id), auditor)


@router.delete("/{decision_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_decision(decision_id: int, db: DbDep, workspace: WorkspaceDep) -> Response:
    db.delete(get_decision_or_404(db, workspace, decision_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{decision_id}/audit", response_model=DecisionDetail)
def retry_audit(
    decision_id: int, db: DbDep, workspace: WorkspaceDep, auditor: AuditorDep
) -> DecisionDetail:
    decision = get_decision_or_404(db, workspace, decision_id)
    if decision.outcome is not None:
        # Re-extracting assumptions after the outcome is known is exactly the hindsight bias
        # this app exists to prevent.
        raise HTTPException(status.HTTP_409_CONFLICT, "Can't re-audit a decision after its review.")
    traces = TraceBuffer(workspace, decision.id)
    try:
        run_audit(db, decision, auditor, traces)
    finally:
        traces.flush(db)
    return to_detail(db, decision, auditor)


@router.post(
    "/{decision_id}/outcome", response_model=DecisionDetail, status_code=status.HTTP_201_CREATED
)
def record_outcome(
    decision_id: int,
    body: OutcomeCreate,
    db: DbDep,
    workspace: WorkspaceDep,
    auditor: AuditorDep,
) -> DecisionDetail:
    decision = get_decision_or_404(db, workspace, decision_id)
    if decision.outcome is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This decision already has an outcome.")
    decision.outcome = Outcome(happened=body.happened, what_happened=body.what_happened)
    db.commit()

    traces = TraceBuffer(workspace, decision.id)
    try:
        run_review(db, decision, auditor, traces)
    finally:
        traces.flush(db)
    return to_detail(db, decision, auditor)


@router.post("/{decision_id}/review", response_model=DecisionDetail)
def retry_review(
    decision_id: int, db: DbDep, workspace: WorkspaceDep, auditor: AuditorDep
) -> DecisionDetail:
    decision = get_decision_or_404(db, workspace, decision_id)
    if decision.outcome is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Record an outcome before reviewing.")
    traces = TraceBuffer(workspace, decision.id)
    try:
        run_review(db, decision, auditor, traces)
    finally:
        traces.flush(db)
    return to_detail(db, decision, auditor)
