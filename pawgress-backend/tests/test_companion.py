"""
tests/test_companion.py — FR-6.1, FR-6.2/Invariant 6, §10.2 CatMoodStateCalculator.
"""

import uuid as uuid_mod
from datetime import datetime, timedelta, timezone


def test_companion_state_requires_auth(client):
    response = client.get("/companion/state")
    assert response.status_code == 403


def test_new_user_with_no_activity_is_neutral(client, auth_headers):
    """FR-6.2/AC-6.2.1's spirit applied to day one: zero history is a
    neutral baseline, never a diminished/negative state."""
    response = client.get("/companion/state", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["mood"] == "Neutral"


def test_activity_today_is_content(client, auth_headers):
    client.post("/tasks", json={"title": "Something"}, headers=auth_headers)
    response = client.get("/companion/state", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["mood"] == "Content"


def test_historical_activity_with_nothing_today_is_attentive(client, auth_headers, session_factory):
    """A user with real history but no activity in today's window lands on
    ATTENTIVE, not a diminished/negative state — Invariant 6: mood is never
    selected by an inactivity-only signal, and Attentive is not rendered or
    treated as 'sadder' than Content anywhere in this implementation."""
    import jose.jwt as jwt
    from shared.config import settings
    from productivity.models import Task, TaskOrigin, Priority

    token = auth_headers["Authorization"].split(" ")[1]
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    user_id = uuid_mod.UUID(payload["sub"])

    db = session_factory()
    try:
        old_task = Task(
            id=uuid_mod.uuid4(),
            user_id=user_id,
            title="Old task",
            category=None,
            priority=Priority.MEDIUM,
            estimate_minutes=None,
            origin=TaskOrigin.MANUALLY_CREATED,
            source_capture_id=None,
        )
        db.add(old_task)
        db.commit()
        # Back-date it to well before today's UTC boundary.
        db.query(Task).filter(Task.id == old_task.id).update(
            {Task.created_at: datetime.now(timezone.utc) - timedelta(days=5)}
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/companion/state", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["mood"] == "Attentive"


def test_companion_never_writes_to_task_or_capture(client, auth_headers, session_factory):
    """Domain Model §10.2 — CatMoodStateCalculator reads Task/Capture
    history but never writes to it. Verified by confirming task state is
    byte-for-byte unchanged after repeated companion-state reads."""
    create_response = client.post("/tasks", json={"title": "Untouched"}, headers=auth_headers)
    task_before = create_response.json()

    for _ in range(3):
        client.get("/companion/state", headers=auth_headers)

    list_response = client.get("/tasks", headers=auth_headers)
    task_after = next(t for t in list_response.json() if t["id"] == task_before["id"])
    assert task_after == task_before


def test_companion_state_is_scoped_to_the_authenticated_user(client, auth_headers, second_user_headers):
    """A second user's activity must never influence the first user's mood
    — Companion state is per-user, same as every other resource."""
    client.post("/tasks", json={"title": "Active user's task"}, headers=auth_headers)

    response = client.get("/companion/state", headers=second_user_headers)
    assert response.status_code == 200
    assert response.json()["mood"] == "Neutral"
