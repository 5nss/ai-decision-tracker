# server/schemas.py
"""Pydantic schemas for API request and response bodies.
These are minimal definitions; you can extend as needed.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
import datetime

class DecisionBase(BaseModel):
    user_id: int = Field(..., description="ID of the user creating the decision")
    decision_text: str = Field(..., description="Short description of the decision")
    reasoning: str = Field(..., description="Structured reasoning behind the decision")
    expected_outcome: str = Field(..., description="What the user expects to happen")
    constraints: Optional[str] = None
    timestamp: Optional[datetime.datetime] = None

class DecisionCreate(DecisionBase):
    pass

class Decision(DecisionBase):
    id: int
    timestamp: datetime.datetime
    class Config:
        from_attributes = True

class OutcomeBase(BaseModel):
    decision_id: int = Field(..., description="Foreign key to the decision")
    actual_outcome: str = Field(..., description="What actually happened")
    context: Optional[str] = None
    timestamp: Optional[datetime.datetime] = None

class OutcomeCreate(OutcomeBase):
    pass

class Outcome(OutcomeBase):
    id: int
    timestamp: datetime.datetime
    class Config:
        from_attributes = True

# ---- New schemas ----
class FeatureBase(BaseModel):
    decision_id: int = Field(..., description="Foreign key to the decision")
    assumptions: Optional[str] = None
    constraints_ignored: Optional[bool] = None
    domain: Optional[str] = None
    outcome_quality: Optional[str] = None

class FeatureCreate(FeatureBase):
    pass

class Feature(FeatureBase):
    id: int
    class Config:
        from_attributes = True

class BehaviorBase(BaseModel):
    user_id: int = Field(..., description="User to which the behavior belongs")
    behavior: str = Field(..., description="Behavior tag or description")
    frequency: int = Field(..., description="Number of occurrences")
    confidence: float = Field(..., description="Confidence score (0‑1)")
    last_seen: datetime.datetime = Field(..., description="Timestamp of last occurrence")

class BehaviorCreate(BehaviorBase):
    pass

class Behavior(BehaviorBase):
    id: int
    class Config:
        from_attributes = True
