"""
shared/database.py

One database engine and session factory, shared by every module. Modules define
their own tables (see identity/models.py, productivity/models.py) but all of them
go through this single connection setup — consistent with System Architecture §8's
"single Postgres instance as the system of record" decision.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from shared.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Every model in every module inherits from this same Base, so a single
# `Base.metadata.create_all(engine)` call (see scripts/init_db.py) creates
# every table across all modules in one step.
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session per request, always closes it
    afterward even if the request raised an exception."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
