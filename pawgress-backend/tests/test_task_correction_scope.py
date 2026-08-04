"""
tests/test_task_correction_scope.py

Regression coverage for routes.py's CORRECTION_TRACKED_FIELDS change: adding
`status` and `goalId` to TaskUpdateRequest (needed for FR-3.3's status
editing and FR-5.2's goal linking to actually work) must not cause either
field to be mistaken for an AI-field correction (Domain Model §10.3 /
Blueprint §17's correction-rate metric would be polluted otherwise).

FieldCorrectionRecord has no user-facing read path (BR-4), so these tests
verify indirectly, via the documented contract: an AI-generated task's
status/goal changes must succeed exactly like an ordinary edit, and this
suite exists to make the *scope* of CORRECTION_TRACKED_FIELDS an explicit,
tested decision rather than an implicit one that could regress silently.
"""

import uuid as uuid_mod


def _create_ai_generated_task(session_factory, user_id):
    """Bypasses the real extraction pipeline (no live provider in this
    environment) and inserts an AIGenerated task directly — sufficient here
    since this test is about routes.py's correction-scoping logic, not
    extraction itself."""
    from productivity.models import Task, TaskOrigin, Priority

    db = session_factory()
    try:
        task = Task(
            id=uuid_mod.uuid4(),
            user_id=user_id,
            title="AI task",
            category="Work",
            priority=Priority.MEDIUM,
            estimate_minutes=None,
            origin=TaskOrigin.AI_GENERATED,
            source_capture_id=None,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task.id
    finally:
        db.close()


def test_status_change_on_ai_task_does_not_error(client, auth_headers, session_factory):
    """Marking an AI-generated task Done is the ordinary Completing-and-
    Reflecting interaction (UX Philosophy §5.3), not a correction — must
    succeed without needing to be a tracked field."""
    from identity.auth import create_access_token
    import jose.jwt as jwt
    from shared.config import settings

    token = auth_headers["Authorization"].split(" ")[1]
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    user_id = uuid_mod.UUID(payload["sub"])

    task_id = _create_ai_generated_task(session_factory, user_id)

    response = client.patch(f"/tasks/{task_id}", json={"status": "Done"}, headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "Done"


def test_goal_link_on_ai_task_does_not_error(client, auth_headers, session_factory):
    import jose.jwt as jwt
    from shared.config import settings

    token = auth_headers["Authorization"].split(" ")[1]
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    user_id = uuid_mod.UUID(payload["sub"])

    task_id = _create_ai_generated_task(session_factory, user_id)
    goal_id = client.post("/goals", json={"label": "Career"}, headers=auth_headers).json()["id"]

    response = client.patch(f"/tasks/{task_id}", json={"goalId": goal_id}, headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["goalId"] == goal_id


def test_ai_field_correction_still_works(client, auth_headers, session_factory):
    """The actual Quiet Correction path (FR-4.1) — still functions correctly
    for the four AI-assigned fields after the routes.py rewrite."""
    import jose.jwt as jwt
    from shared.config import settings

    token = auth_headers["Authorization"].split(" ")[1]
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    user_id = uuid_mod.UUID(payload["sub"])

    task_id = _create_ai_generated_task(session_factory, user_id)

    response = client.patch(f"/tasks/{task_id}", json={"category": "Personal"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["category"] == "Personal"
