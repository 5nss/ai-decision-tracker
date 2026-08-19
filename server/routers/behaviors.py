# server/routers/behaviors.py
"""FastAPI router for behavior aggregation — the long-term memory layer.

When an outcome is submitted and features are extracted, this engine:
  1. Looks at all features for the user's decisions
  2. Identifies recurring patterns (e.g. ignoring constraints, poor outcomes in 'work' domain)
  3. Upserts behavior records with updated frequency + confidence scores

Behaviors are probabilistic — they describe tendencies, not absolute truths.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
import datetime
from collections import defaultdict
from typing import Optional

from .. import schemas, models, database

router = APIRouter()


# ── Behavior pattern rules ──────────────────────────────────────────────────────
# Each rule maps to a human-readable behavior tag and a function that detects it
# from a Feature record.

def _behavior_signals(feature: models.Feature) -> list[str]:
    """Return list of behavior tags detected from a single Feature record."""
    tags: list[str] = []

    if feature.constraints_ignored:
        tags.append("ignores_constraints")

    if feature.outcome_quality == "poor":
        tags.append("poor_outcome_track_record")

    if feature.outcome_quality == "good":
        tags.append("good_outcome_track_record")

    if feature.assumptions:
        assumption_count = len(feature.assumptions.split(";"))
        if assumption_count >= 3:
            tags.append("over_assumes")
        elif assumption_count >= 1:
            tags.append("makes_assumptions")

    if feature.domain:
        tags.append(f"active_in_{feature.domain}")

    return tags


def _confidence_score(frequency: int, total_decisions: int) -> float:
    """Bayesian-ish confidence: higher frequency relative to total = higher confidence."""
    if total_decisions == 0:
        return 0.0
    raw = frequency / total_decisions
    # Dampen confidence below 3 occurrences (cold start)
    dampening = min(1.0, frequency / 3)
    return round(raw * dampening, 3)


# ── Aggregation engine ──────────────────────────────────────────────────────────

def aggregate_behaviors_for_user(user_id: int, db: Session) -> list[models.Behavior]:
    """
    Full re-aggregation of behavior patterns for a user from their features.
    Upserts behavior rows — creates new ones or updates existing ones.
    """
    # Get all decisions by this user
    decisions = db.query(models.Decision).filter(models.Decision.user_id == user_id).all()
    if not decisions:
        return []

    decision_ids = [d.id for d in decisions]
    total_decisions = len(decision_ids)

    # Get all features for those decisions
    features = db.query(models.Feature).filter(
        models.Feature.decision_id.in_(decision_ids)
    ).all()

    # Tally behavior signals
    tally: dict[str, int] = defaultdict(int)
    latest_seen: dict[str, datetime.datetime] = {}

    for feat in features:
        signals = _behavior_signals(feat)
        for tag in signals:
            tally[tag] += 1
            # Use feature's timestamp (or now as fallback)
            ts = getattr(feat, "timestamp", None) or datetime.datetime.utcnow()
            if tag not in latest_seen or ts > latest_seen[tag]:
                latest_seen[tag] = ts

    # Upsert behavior rows
    updated: list[models.Behavior] = []
    for tag, freq in tally.items():
        confidence = _confidence_score(freq, total_decisions)
        seen_at = latest_seen.get(tag, datetime.datetime.utcnow())

        existing = db.query(models.Behavior).filter(
            models.Behavior.user_id == user_id,
            models.Behavior.behavior == tag,
        ).first()

        if existing:
            existing.frequency = freq
            existing.confidence = confidence
            existing.last_seen = seen_at
            updated.append(existing)
        else:
            new_beh = models.Behavior(
                user_id=user_id,
                behavior=tag,
                frequency=freq,
                confidence=confidence,
                last_seen=seen_at,
            )
            db.add(new_beh)
            updated.append(new_beh)

    db.commit()
    for b in updated:
        db.refresh(b)

    return updated


# ── CRUD + aggregation endpoints ──────────────────────────────────────────────

@router.post("/", response_model=schemas.Behavior, status_code=status.HTTP_201_CREATED)
def create_behavior(behavior: schemas.BehaviorCreate, db: Session = Depends(database.get_db)):
    """Manually insert a behavior record."""
    db_behavior = models.Behavior(**behavior.model_dump())
    db.add(db_behavior)
    db.commit()
    db.refresh(db_behavior)
    return db_behavior


@router.post("/aggregate/{user_id}", response_model=list[schemas.Behavior])
def run_aggregation(user_id: int, db: Session = Depends(database.get_db)):
    """
    Re-aggregate all behavior patterns for a user based on their feature history.
    Call this endpoint after a new outcome is recorded.
    """
    results = aggregate_behaviors_for_user(user_id, db)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No features found for user {user_id} — log some decisions and outcomes first."
        )
    return results


@router.get("/user/{user_id}", response_model=list[schemas.Behavior])
def read_user_behaviors(user_id: int, db: Session = Depends(database.get_db)):
    """Fetch all aggregated behaviors for a user, sorted by confidence descending."""
    return (
        db.query(models.Behavior)
        .filter(models.Behavior.user_id == user_id)
        .order_by(models.Behavior.confidence.desc())
        .all()
    )


@router.get("/", response_model=list[schemas.Behavior])
def read_behaviors(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    return db.query(models.Behavior).offset(skip).limit(limit).all()


@router.get("/{behavior_id}", response_model=schemas.Behavior)
def read_behavior(behavior_id: int, db: Session = Depends(database.get_db)):
    behavior = db.query(models.Behavior).filter(models.Behavior.id == behavior_id).first()
    if not behavior:
        raise HTTPException(status_code=404, detail="Behavior not found")
    return behavior
