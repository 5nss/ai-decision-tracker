"""Audit a decision right after it's logged: embed it, retrieve similar reviewed decisions, ask the
auditor for assumptions, and save the result.

Two rules shape this module:
  1. Commit before every network call, so no SQLite write lock is held while waiting on a model.
  2. A failed audit never loses the decision. The row is already committed by the caller; a
     failure only sets audit_status="failed" with the reason, and the UI offers a retry.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from typing import TypeVar

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..ai import Auditor, AuditorError, Tracer
from ..ai.types import AuditResult, DecisionInput, PastCase
from ..models import Assumption, Decision
from .retrieval import embedding_text, similar_reviewed, to_blob

log = logging.getLogger(__name__)
_T = TypeVar("_T")

SIMILAR_K = 3
MAX_ASSUMPTIONS = 5
MAX_NOTES = 3


def decision_input(d: Decision) -> DecisionInput:
    return DecisionInput(
        title=d.title,
        reasoning=d.reasoning,
        alternatives=d.alternatives,
        expected_outcome=d.expected_outcome,
        confidence=d.confidence,
        domain=d.domain,
        review_at=d.review_at.isoformat(),
    )


def _text(d: Decision) -> str:
    return embedding_text(d.title, d.reasoning, d.expected_outcome)


def ensure_embedding(db: Session, decision: Decision, auditor: Auditor, tracer: Tracer) -> bool:
    if decision.embedding is not None and decision.embedding_model == auditor.embed_model:
        return True
    try:
        [vector] = auditor.embed([_text(decision)], tracer=tracer)
    except Exception as exc:  # degrade: audit still runs, just without past cases
        log.warning("embedding failed for decision %s: %s", decision.id, exc)
        return False
    decision.embedding = to_blob(vector)
    decision.embedding_model = auditor.embed_model
    db.commit()
    return True


def past_cases(db: Session, decision: Decision, auditor: Auditor) -> list[PastCase]:
    hits = similar_reviewed(db, decision, SIMILAR_K, auditor.similarity_threshold)
    return [
        PastCase(
            decision_id=d.id,
            title=d.title,
            happened=d.outcome.happened,
            failed_assumptions=[a.text for a in d.assumptions if a.verdict == "failed"],
            similarity=round(score, 3),
        )
        for d, score in hits
    ]


def apply_audit(
    decision: Decision, result: AuditResult, past: list[PastCase], provider_label: str
) -> None:
    decision.assumptions.clear()
    kept = [a for a in result.assumptions if a.text.strip()][:MAX_ASSUMPTIONS]
    for position, a in enumerate(kept):
        decision.assumptions.append(
            Assumption(
                position=position,
                text=a.text.strip(),
                category=str(a.category),
                risk=str(a.risk),
            )
        )
    decision.missing_considerations = [
        m.strip() for m in result.missing_considerations if m.strip()
    ][:MAX_NOTES]
    decision.premortem = result.premortem.strip() or None

    # Only keep warnings that cite a decision the model was actually shown. It's a cheap guard
    # against invented citations.
    shown = {p.decision_id for p in past}
    decision.repeat_warnings = [
        w.model_dump() for w in result.repeat_warnings if w.past_decision_id in shown
    ][:MAX_NOTES]

    decision.audit_status = "done"
    decision.audit_error = None
    decision.audit_provider = provider_label


def run_audit(db: Session, decision: Decision, auditor: Auditor, tracer: Tracer) -> None:
    has_vector = ensure_embedding(db, decision, auditor, tracer)
    past = past_cases(db, decision, auditor) if has_vector else []
    try:
        result = auditor.audit(decision_input(decision), past, tracer=tracer)
    except Exception as exc:
        if not isinstance(exc, AuditorError):
            log.exception("unexpected error while auditing decision %s", decision.id)
        decision.audit_status = "failed"
        decision.audit_error = str(exc)[:500]
        db.commit()
        return
    apply_audit(decision, result, past, auditor.label)
    db.commit()


def _chunks(items: Sequence[_T], size: int) -> Iterator[Sequence[_T]]:
    # itertools.batched would do this, but it needs Python 3.12.
    for start in range(0, len(items), size):
        yield items[start : start + size]


def reembed_stale(
    db: Session, auditor: Auditor, tracer: Tracer, workspace: str | None = None, batch: int = 50
) -> int:
    """(Re)embed rows with no vector, or a vector from a different model (e.g. a key was added)."""
    stmt = select(Decision).where(
        or_(Decision.embedding.is_(None), Decision.embedding_model != auditor.embed_model)
    )
    if workspace:
        stmt = stmt.where(Decision.workspace == workspace)
    rows = list(db.scalars(stmt).all())
    done = 0
    for chunk in _chunks(rows, batch):
        try:
            vectors = auditor.embed([_text(d) for d in chunk], tracer=tracer)
        except Exception as exc:
            log.warning("re-embedding stopped after %d rows: %s", done, exc)
            break
        for d, vector in zip(chunk, vectors, strict=True):
            d.embedding = to_blob(vector)
            d.embedding_model = auditor.embed_model
        db.commit()
        done += len(chunk)
    return done
