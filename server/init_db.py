# server/init_db.py
"""Create all tables in the SQLite/PostgreSQL database.
Run this once to generate tables.
"""
from .database import engine, Base
from . import models

def main() -> None:
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    main()
