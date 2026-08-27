"""
shared/database.py

One database engine and session factory, shared by every module. Modules define
their own tables (see identity/models.py, productivity/models.py) but all of them
go through this single connection setup — consistent with System Architecture §8's
"single Postgres instance as the system of record" decision.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base

from shared.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Every model in every module inherits from this same Base, so a single
# `Base.metadata.create_all(engine)` call (see scripts/init_db.py) creates
# every table across all modules in one step.
Base = declarative_base()


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """Postgres (the real, production database — System Architecture §8)
    enforces foreign key constraints, including ON DELETE CASCADE, out of
    the box. SQLite does NOT, unless this pragma is set on every
    connection — without it, habits/models.py's deliberate cascade-delete
    from Habit to HabitCompletion would silently no-op in the SQLite test
    harness (tests/conftest.py), meaning the test suite could pass for the
    wrong reason (or fail) without this actually exercising real
    referential-integrity behavior.

    Registered on the Engine *class*, not a specific engine instance,
    because the test harness constructs its own SQLite engines directly
    (tests/conftest.py's db_engine fixture) rather than importing the
    module-level `engine` above — a class-level listener applies to every
    engine created anywhere in the process, including those. No effect on
    Postgres connections (guarded by dialect name), so production behavior
    is unchanged."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db():
    """FastAPI dependency — yields a DB session per request, always closes it
    afterward even if the request raised an exception."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
