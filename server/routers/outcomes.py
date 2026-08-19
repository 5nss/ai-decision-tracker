# server/routers/outcomes.py
"""FastAPI router for outcome CRUD operations.

When an outcome is created, the system automatically:
  1. Extracts features from the decision + outcome pair (Feature Memory Layer)
  2. Re-aggregates the user's behavior patterns (Behavior Memory Layer)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import schemas, models, database
from .features import auto_extract_and_save
from .behaviors import aggregate_behaviors_for_user

router = APIRouter()


@router.post("/", response_model=schemas.Outcome, status_code=status.HTTP_201_CREATED)
def create_outcome(outcome: schemas.OutcomeCreate, db: Session = Depends(database.get_db)):
    """
    Record the actual outcome for a decision.

    Side-effects (automatic, background):
      - Extracts features (assumptions, domain, outcome quality)
      - Re-aggregates behavioral patterns for the decision's user
    """
    # 1. Verify the referenced decision exists
    decision = db.query(models.Decision).filter(models.Decision.id == outcome.decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    # 2. Save the outcome
    db_outcome = models.Outcome(**outcome.model_dump())
    db.add(db_outcome)
    db.commit()
    db.refresh(db_outcome)

    # 3. Auto-extract features (silently — don't fail the request if this errors)
    try:
        auto_extract_and_save(decision, db_outcome, db)
    except Exception:
        pass  # Feature extraction failure should never break outcome recording

    # 4. Re-aggregate behaviors for the user (silently)
    try:
        aggregate_behaviors_for_user(decision.user_id, db)
    except Exception:
        pass

    return db_outcome


@router.get("/", response_model=list[schemas.Outcome])
def read_outcomes(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    return db.query(models.Outcome).offset(skip).limit(limit).all()


@router.get("/decision/{decision_id}", response_model=list[schemas.Outcome])
def read_outcomes_for_decision(decision_id: int, db: Session = Depends(database.get_db)):
    """Get all outcomes for a specific decision."""
    return db.query(models.Outcome).filter(
        models.Outcome.decision_id == decision_id
    ).all()


@router.get("/{outcome_id}", response_model=schemas.Outcome)
def read_outcome(outcome_id: int, db: Session = Depends(database.get_db)):
    outcome = db.query(models.Outcome).filter(models.Outcome.id == outcome_id).first()
    if not outcome:
        raise HTTPException(status_code=404, detail="Outcome not found")
    return outcome
