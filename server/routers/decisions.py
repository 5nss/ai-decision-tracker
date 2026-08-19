# server/routers/decisions.py
"""FastAPI router for decision CRUD operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import schemas, models, database

router = APIRouter()

@router.post("/", response_model=schemas.Decision, status_code=status.HTTP_201_CREATED)
def create_decision(decision: schemas.DecisionCreate, db: Session = Depends(database.get_db)):
    db_decision = models.Decision(**decision.model_dump())
    db.add(db_decision)
    db.commit()
    db.refresh(db_decision)
    return db_decision

@router.get("/", response_model=list[schemas.Decision])
def read_decisions(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    decisions = db.query(models.Decision).offset(skip).limit(limit).all()
    return decisions

@router.get("/{decision_id}", response_model=schemas.Decision)
def read_decision(decision_id: int, db: Session = Depends(database.get_db)):
    decision = db.query(models.Decision).filter(models.Decision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision
