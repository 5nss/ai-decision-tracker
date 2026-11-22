"""Judge a decision's assumptions once its outcome is known."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..ai import Auditor, AuditorError, Tracer
from ..ai.text import normalize_for_match
from ..ai.types import AssumptionToJudge, Category
from ..models import Decision
from .audit import decision_input, run_audit

log = logging.getLogger(__name__)


def is_grounded(evidence: str, notes: str) -> bool:
    """Is the evidence quote really in the user's notes? Compared on normalized word tokens, so
    case, punctuation and curly quotes don't matter but invented wording does."""
    quote = normalize_for_match(evidence)
    return bool(quote) and quote in normalize_for_match(notes)


def _category(value: str) -> Category:
    try:
        return Category(value)
    except ValueError:
        return Category.OTHER


def run_review(db: Session, decision: Decision, auditor: Auditor, tracer: Tracer) -> None:
    outcome = decision.outcome
    if outcome is None:
        raise ValueError("run_review needs an outcome")

    # If the audit never succeeded, extract assumptions now. That's still free of hindsight:
    # extraction only reads the original reasoning, never the outcome.
    if decision.audit_status != "done":
        run_audit(db, decision, auditor, tracer)

    if not decision.assumptions:
        outcome.review_status = "done"
        outcome.review_error = None
        db.commit()
        return

    to_judge = [
        AssumptionToJudge(id=a.id, text=a.text, category=_category(a.category))
        for a in decision.assumptions
    ]
    try:
        result = auditor.review(
            decision_input(decision),
            to_judge,
            outcome.happened,
            outcome.what_happened,
            tracer=tracer,
        )
    except Exception as exc:
        if not isinstance(exc, AuditorError):
            log.exception("unexpected error while reviewing decision %s", decision.id)
        outcome.review_status = "failed"
        outcome.review_error = str(exc)[:500]
        db.commit()
        return

    by_id = {v.assumption_id: v for v in result.verdicts}
    for assumption in decision.assumptions:
        verdict = by_id.get(assumption.id)
        if verdict is None:  # the model skipped it, so treat it as unknown rather than guessing
            assumption.verdict = "unclear"
            assumption.evidence = None
            assumption.evidence_grounded = None
            continue
        evidence = verdict.evidence.strip().strip("\"'“”") or None
        assumption.verdict = str(verdict.verdict)
        assumption.evidence = evidence
        assumption.evidence_grounded = (
            is_grounded(evidence, outcome.what_happened) if evidence else None
        )

    outcome.lesson = result.lesson.strip() or None
    outcome.review_status = "done"
    outcome.review_error = None
    db.commit()
