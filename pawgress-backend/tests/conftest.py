"""
tests/conftest.py

Test env vars must be set before ANY app module import — shared/config.py
reads them at import time (settings is a module-level singleton), and
shared/database.py creates its engine at import time too. Both happen as a
side effect of `import main`, so this file sets them at the very top,
before any local import below it.

Uses SQLite (file-per-test-run, not the production Postgres) — fine for
these tests since nothing here exercises Postgres-specific behavior; the
Domain Model's invariants are enforced in application code (routes.py,
goal_service.py), not via DB-specific constraints, so SQLite is a faithful
enough substitute for integration-testing the API layer.
"""

import os
import uuid

os.environ.setdefault("DATABASE_URL", f"sqlite:////tmp/pawgress_test_{uuid.uuid4().hex}.db")
os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")
os.environ.setdefault("FRONTEND_ORIGIN", "http://127.0.0.1:5173")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.database import Base, get_db
from shared.config import settings
from shared.rate_limit import login_rate_limiter, register_rate_limiter, password_reset_rate_limiter
import identity.models  # noqa: F401 — registers User on Base.metadata
import productivity.models  # noqa: F401 — registers Task/Goal/Capture/etc.
import main as main_module


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """The rate limiters added 2026-09-13 (shared/rate_limit.py) are
    module-level singletons, and FastAPI's TestClient makes every request
    in every test appear to come from the same client IP — without this,
    the FIRST test file to run enough register/login calls would start
    getting real 429s from the SECOND file's tests too, entirely by
    accident, since they're not otherwise isolated from each other. This
    autouse fixture makes each test start with a clean bucket regardless
    of what ran before it, same as db_engine already does for the
    database."""
    login_rate_limiter.reset()
    register_rate_limiter.reset()
    password_reset_rate_limiter.reset()
    yield


@pytest.fixture()
def db_engine():
    """Fresh SQLite file per test — avoids any cross-test state bleed that
    an in-memory :memory: DB would risk under TestClient's request handling."""
    engine = create_engine(
        f"sqlite:////tmp/pawgress_test_{uuid.uuid4().hex}.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def session_factory(db_engine):
    """Exposed separately from `client` so tests that need to drive domain
    services directly (e.g. run_extraction, to test Task/Capture deletion
    independence without a live LLM provider) can open a session against the
    exact same engine/tables the TestClient is using, rather than the
    module-level `shared.database.engine` singleton (which is bound to a
    different, untouched DB file in this test environment)."""
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    """Registers a fresh user and returns Authorization headers for it —
    every productivity endpoint requires auth (System Architecture §9)."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    response = client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def second_user_headers(client):
    """A distinct authenticated user — used to test cross-user isolation
    (Domain Model Invariant 1, 3, 8)."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    response = client.post("/auth/register", json={"email": email, "password": "another-horse-battery"})
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
