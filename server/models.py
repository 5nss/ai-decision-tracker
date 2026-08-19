# server/models.py
"""SQLAlchemy ORM models matching the Pydantic schemas"
Only the core tables are defined here; you can extend with indexes, constraints, etc.
"""


from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.sql import func
from .database import Base

class Decision(Base):
    __tablename__ = "decisions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    decision_text = Column(String(255), nullable=False)
    reasoning = Column(Text, nullable=False)
    expected_outcome = Column(Text, nullable=False)
    constraints = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class Outcome(Base):
    __tablename__ = "outcomes"
    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=False, index=True)
    actual_outcome = Column(Text, nullable=False)
    context = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

# Feature model for extracted features per decision
class Feature(Base):
    __tablename__ = "features"
    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=False, index=True)
    assumptions = Column(Text, nullable=True)
    constraints_ignored = Column(Integer, nullable=True)  # 0/1 flag
    domain = Column(String(100), nullable=True)
    outcome_quality = Column(String(100), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

# Behavior model for aggregated long‑term patterns
class Behavior(Base):
    __tablename__ = "behaviors"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    behavior = Column(String(200), nullable=False)
    frequency = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    last_seen = Column(DateTime(timezone=True), server_default=func.now())


