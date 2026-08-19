# server/routers/features.py
"""FastAPI router for feature extraction per decision.

Features are the intermediate memory layer:
  - assumptions    : what the user assumed (extracted from reasoning text)
  - constraints_ignored : whether constraints field was empty / skipped
  - domain         : topic domain heuristic (study, work, habit, finance, social, other)
  - outcome_quality: good / mixed / poor — derived from comparing expected vs actual outcome
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import re

from .. import schemas, models, database

router = APIRouter()


# ── Domain heuristics ─────────────────────────────────────────────────────────
_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "study":   ["study", "learn", "exam", "course", "class", "assignment", "research", "book", "read"],
    "work":    ["work", "project", "deadline", "meeting", "job", "career", "client", "task", "sprint"],
    "habit":   ["habit", "routine", "daily", "morning", "exercise", "sleep", "diet", "health", "gym"],
    "finance": ["money", "invest", "budget", "spend", "save", "cost", "price", "salary", "expense"],
    "social":  ["friend", "family", "relationship", "talk", "meet", "event", "party", "team", "colleague"],
}

def _detect_domain(text: str) -> str:
    text_lower = text.lower()
    scores = {domain: sum(1 for kw in kws if kw in text_lower)
              for domain, kws in _DOMAIN_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "other"


# ── Assumption extraction ──────────────────────────────────────────────────────
def _extract_assumptions(reasoning: str) -> Optional[str]:
    """Pull sentences containing assumption-signal words from reasoning text."""
    signals = ["assume", "expect", "think", "believe", "hope", "should", "probably", "likely", "will be"]
    sentences = re.split(r'[.!?]', reasoning)
    hits = [s.strip() for s in sentences if any(sig in s.lower() for sig in signals)]
    return "; ".join(hits) if hits else None


# ── Outcome quality assessment ─────────────────────────────────────────────────
def _assess_outcome_quality(expected: str, actual: str) -> str:
    """Heuristic comparison of expected vs actual outcome text."""
    exp_words = set(expected.lower().split())
    act_words = set(actual.lower().split())
    if not exp_words:
        return "unknown"

    overlap = len(exp_words & act_words) / len(exp_words)

    # Look for negative signal words in actual outcome
    negative_signals = ["fail", "didn't", "could not", "worse", "bad", "wrong", "mistake",
                        "not", "never", "miss", "disappoint", "problem", "issue"]
    negative_hit = any(sig in actual.lower() for sig in negative_signals)

    if negative_hit and overlap < 0.25:
        return "poor"
    elif overlap >= 0.45 and not negative_hit:
        return "good"
    else:
        return "mixed"


# ── Auto-extract features from a decision + outcome pair ──────────────────────
def auto_extract_and_save(
    decision: models.Decision,
    outcome: models.Outcome,
    db: Session,
) -> models.Feature:
    """Create a Feature record automatically when an outcome is recorded."""

    # Check if a feature already exists for this decision
    existing = db.query(models.Feature).filter(
        models.Feature.decision_id == decision.id
    ).first()
    if existing:
        return existing  # idempotent — don't double-extract

    assumptions = _extract_assumptions(decision.reasoning)
    constraints_ignored = 1 if not decision.constraints else 0
    domain = _detect_domain(f"{decision.decision_text} {decision.reasoning}")
    quality = _assess_outcome_quality(decision.expected_outcome, outcome.actual_outcome)

    feature = models.Feature(
        decision_id=decision.id,
        assumptions=assumptions,
        constraints_ignored=bool(constraints_ignored),
        domain=domain,
        outcome_quality=quality,
    )
    db.add(feature)
    db.commit()
    db.refresh(feature)
    return feature


# ── CRUD endpoints ────────────────────────────────────────────────────────────

@router.post("/", response_model=schemas.Feature, status_code=status.HTTP_201_CREATED)
def create_feature(feature: schemas.FeatureCreate, db: Session = Depends(database.get_db)):
    """Manually create a feature record for a decision."""
    decision = db.query(models.Decision).filter(models.Decision.id == feature.decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    db_feature = models.Feature(**feature.model_dump())
    db.add(db_feature)
    db.commit()
    db.refresh(db_feature)
    return db_feature


@router.get("/", response_model=list[schemas.Feature])
def read_features(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    return db.query(models.Feature).offset(skip).limit(limit).all()


@router.get("/decision/{decision_id}", response_model=list[schemas.Feature])
def read_features_for_decision(decision_id: int, db: Session = Depends(database.get_db)):
    """Get all features extracted for a specific decision."""
    return db.query(models.Feature).filter(models.Feature.decision_id == decision_id).all()


@router.get("/{feature_id}", response_model=schemas.Feature)
def read_feature(feature_id: int, db: Session = Depends(database.get_db)):
    feature = db.query(models.Feature).filter(models.Feature.id == feature_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature
