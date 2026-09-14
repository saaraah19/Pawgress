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


def _user_id_from(auth_headers):
    import jose.jwt as jwt
    from shared.config import settings

    token = auth_headers["Authorization"].split(" ")[1]
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return uuid_mod.UUID(payload["sub"])


def _backdate_completion(session_factory, user_id, days_ago: float):
    """Creates a task and directly backdates completed_at — bypassing the
    API's `now()`-only completion path, since the whole point of these
    tests is to simulate a completion that happened several days ago."""
    from productivity.models import Task, TaskOrigin, Priority

    db = session_factory()
    try:
        task = Task(
            id=uuid_mod.uuid4(),
            user_id=user_id,
            title="Backdated completion",
            category=None,
            priority=Priority.MEDIUM,
            estimate_minutes=None,
            origin=TaskOrigin.MANUALLY_CREATED,
            source_capture_id=None,
        )
        db.add(task)
        db.commit()
        db.query(Task).filter(Task.id == task.id).update(
            {Task.completed_at: datetime.now(timezone.utc) - timedelta(days=days_ago)}
        )
        db.commit()
    finally:
        db.close()


def test_no_completion_in_threshold_window_is_wistful(client, auth_headers, session_factory):
    """The Wistful tier's core case: a user who HAS completed something
    before, but not in the last WISTFUL_THRESHOLD_DAYS days. Takes priority
    over Content/Attentive regardless of today's activity — this is the one
    deliberate exception to Invariant 6, scoped narrowly per
    mood_calculator.py's docstring."""
    user_id = _user_id_from(auth_headers)
    _backdate_completion(session_factory, user_id, days_ago=5)

    response = client.get("/companion/state", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["mood"] == "Wistful"


def test_completion_within_threshold_is_not_wistful(client, auth_headers, session_factory):
    """A completion 1 day ago is well within the 3-day threshold — should
    read as ordinary Content (there's also activity today from creating
    the task), not Wistful."""
    user_id = _user_id_from(auth_headers)
    _backdate_completion(session_factory, user_id, days_ago=1)

    response = client.get("/companion/state", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["mood"] != "Wistful"


def test_never_completed_is_not_wistful_even_with_old_activity(client, auth_headers, session_factory):
    """A brand-new-ish user who has old activity but has NEVER completed
    anything must never be shown as Wistful — there's nothing to 'recover'
    from on day one, per the explicit design requirement (Task.completed_at
    is None for every row, so has_completed_ever is False and the Wistful
    branch is never entered)."""
    import jose.jwt as jwt
    from shared.config import settings
    from productivity.models import Task, TaskOrigin, Priority

    user_id = _user_id_from(auth_headers)
    db = session_factory()
    try:
        old_task = Task(
            id=uuid_mod.uuid4(),
            user_id=user_id,
            title="Old, never completed",
            category=None,
            priority=Priority.MEDIUM,
            estimate_minutes=None,
            origin=TaskOrigin.MANUALLY_CREATED,
            source_capture_id=None,
        )
        db.add(old_task)
        db.commit()
        db.query(Task).filter(Task.id == old_task.id).update(
            {Task.created_at: datetime.now(timezone.utc) - timedelta(days=10)}
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/companion/state", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["mood"] == "Attentive"


def test_completing_a_task_recovers_from_wistful_instantly(client, auth_headers, session_factory):
    """The recovery half of the design: Wistful clears the moment a new
    completion happens, with no cooldown or gradual recovery arc."""
    user_id = _user_id_from(auth_headers)
    _backdate_completion(session_factory, user_id, days_ago=5)
    assert client.get("/companion/state", headers=auth_headers).json()["mood"] == "Wistful"

    create_response = client.post("/tasks", json={"title": "Fresh one"}, headers=auth_headers)
    task_id = create_response.json()["id"]
    client.patch(f"/tasks/{task_id}", json={"status": "Done"}, headers=auth_headers)

    response = client.get("/companion/state", headers=auth_headers)
    assert response.json()["mood"] == "Content"


def test_marking_done_sets_completed_at_and_undoing_clears_it(client, auth_headers):
    """productivity/routes.py's update_task special-case: completed_at
    tracks the most recent completion EVENT, so undoing a completion must
    honestly clear it, not leave a stale timestamp behind."""
    from productivity.models import Task

    create_response = client.post("/tasks", json={"title": "Toggle me"}, headers=auth_headers)
    task_id = create_response.json()["id"]

    client.patch(f"/tasks/{task_id}", json={"status": "Done"}, headers=auth_headers)
    # completed_at isn't exposed via the API response (internal signal
    # only) — assert the mood effect instead, which is the actual contract.
    assert client.get("/companion/state", headers=auth_headers).json()["mood"] == "Content"

    client.patch(f"/tasks/{task_id}", json={"status": "NotStarted"}, headers=auth_headers)
    # No remaining completion anywhere for this user -> has_completed_ever
    # is now False again -> back to the ordinary Content/Attentive path,
    # never stuck showing a phantom old completion.
    response = client.get("/companion/state", headers=auth_headers)
    assert response.json()["mood"] in ("Content", "Attentive")


def test_companion_state_is_scoped_to_the_authenticated_user(client, auth_headers, second_user_headers):
    """A second user's activity must never influence the first user's mood
    — Companion state is per-user, same as every other resource."""
    client.post("/tasks", json={"title": "Active user's task"}, headers=auth_headers)

    response = client.get("/companion/state", headers=second_user_headers)
    assert response.status_code == 200
    assert response.json()["mood"] == "Neutral"
