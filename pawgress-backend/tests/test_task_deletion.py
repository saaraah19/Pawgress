"""
tests/test_task_deletion.py — FR-3.5, AC-3.5.1, Domain Model Invariant 5.
"""


def test_delete_task(client, auth_headers):
    create_response = client.post("/tasks", json={"title": "Delete me"}, headers=auth_headers)
    task_id = create_response.json()["id"]

    delete_response = client.delete(f"/tasks/{task_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    list_response = client.get("/tasks", headers=auth_headers)
    ids = [t["id"] for t in list_response.json()]
    assert task_id not in ids


def test_delete_nonexistent_task_returns_404(client, auth_headers):
    response = client.delete("/tasks/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert response.status_code == 404


def test_cannot_delete_another_users_task(client, auth_headers, second_user_headers):
    """Domain Model Invariant 1/8 — every query is scoped to the owning
    user; another user's task must be invisible, not just protected."""
    create_response = client.post("/tasks", json={"title": "Mine"}, headers=auth_headers)
    task_id = create_response.json()["id"]

    response = client.delete(f"/tasks/{task_id}", headers=second_user_headers)
    assert response.status_code == 404

    # And it's still there for the actual owner.
    list_response = client.get("/tasks", headers=auth_headers)
    ids = [t["id"] for t in list_response.json()]
    assert task_id in ids


def test_delete_requires_auth(client, auth_headers):
    create_response = client.post("/tasks", json={"title": "x"}, headers=auth_headers)
    task_id = create_response.json()["id"]
    # See test_manual_task_creation.py::test_create_task_requires_auth for
    # why this is 403, not 401.
    response = client.delete(f"/tasks/{task_id}")
    assert response.status_code == 403


def test_deleting_task_does_not_touch_its_source_capture(client, auth_headers, session_factory):
    """Domain Model Invariant 5 / Modeling Principle 1 — Task and Capture
    are independently deletable. Drives ExtractionService directly with a
    stubbed provider (no live LLM call in this environment, consistent with
    System Architecture §21: the provider is mocked for application-layer
    tests; live-provider behavior has its own separate evaluation surface),
    against the same DB the `client` fixture is using."""
    import uuid as uuid_mod
    from productivity.extraction_service import run_extraction
    from productivity.models import Capture
    from ai_extraction.provider import ExtractionAttemptResult
    from ai_extraction.schema import ExtractionResponse, ExtractedTask
    from identity.models import User
    from identity.auth import hash_password

    class StubProvider:
        def extract_tasks(self, raw_input: str):
            return ExtractionAttemptResult(
                outcome="success",
                data=ExtractionResponse(
                    tasks=[ExtractedTask(title="Stubbed task", category="Test", priority="Medium", estimateMinutes=None)]
                ),
            )

    db = session_factory()
    try:
        user = User(
            id=uuid_mod.uuid4(),
            email=f"cap_{uuid_mod.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("irrelevant"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        result = run_extraction(db, user.id, "buy milk", StubProvider())
        assert result.capture.status.value == "Succeeded"
        assert len(result.tasks) == 1

        task = result.tasks[0]
        capture_id = task.source_capture_id

        db.delete(task)
        db.commit()

        capture = db.query(Capture).filter(Capture.id == capture_id).first()
        assert capture is not None, "deleting the Task must not delete its source Capture"
        assert capture.raw_text == "buy milk"
    finally:
        db.close()
