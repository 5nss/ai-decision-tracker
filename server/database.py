# server/database.py
"""Database connection using SQLAlchemy.
We use PostgreSQL as defined in the implementation plan.
Replace the DATABASE_URL with your actual connection string or use an .env file.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local_decision_tracker.db")

# Use connect_args only for SQLite database connection
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
#bug 2 is resolved
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
