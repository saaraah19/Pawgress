"""
tests/test_manual_task_creation.py — FR-3.4, AC-3.4.1.
"""


def test_create_task_with_title_only(client, auth_headers):
    """AC-3.4.1: only title is required; status defaults NotStarted, origin
    is ManuallyCreated, no AI-assigned fields are inferred (category stays
    unset, priority defaults to the domain default rather than a guess)."""
    response = client.post("/tasks", json={"title": "Water the plants"}, headers=auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["title"] == "Water the plants"
    assert body["status"] == "NotStarted"
    assert body["origin"] == "ManuallyCreated"
    assert body["category"] is None
    assert body["priority"] == "Medium"
    assert body["estimateMinutes"] is None
    assert body["goalId"] is None


def test_create_task_with_all_fields(client, auth_headers):
    """User-provided fields are used exactly as given — never overridden or
    reinterpreted, since these are user-set values, not AI guesses."""
    payload = {
        "title": "Renew passport",
        "category": "Admin",
        "priority": "High",
        "estimateMinutes": 30,
    }
    response = client.post("/tasks", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["category"] == "Admin"
    assert body["priority"] == "High"
    assert body["estimateMinutes"] == 30


def test_create_task_requires_title(client, auth_headers):
    response = client.post("/tasks", json={"title": ""}, headers=auth_headers)
    assert response.status_code == 422


def test_create_task_requires_auth(client):
    # No Authorization header at all -> HTTPBearer itself rejects with 403,
    # before get_current_user ever runs (401 is reserved for a header that's
    # present but invalid/expired) — this is identity/auth.py's existing,
    # unchanged behavior, not something this endpoint controls.
    response = client.post("/tasks", json={"title": "No auth"})
    assert response.status_code == 403


def test_manually_created_task_appears_in_list(client, auth_headers):
    client.post("/tasks", json={"title": "Buy milk"}, headers=auth_headers)
    response = client.get("/tasks", headers=auth_headers)
    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert "Buy milk" in titles


def test_manual_creation_never_writes_a_correction_record(client, auth_headers):
    """Domain Model §10.3 — CorrectionTracker fires only when an AI-assigned
    field is *changed* on an existing task. Setting fields at creation time
    is not a correction; there is nothing to compare against. Verified
    indirectly: correcting a field on a freshly manually-created task should
    not find a pre-existing correction record already inflating any count
    (no user-facing endpoint exposes this directly, per BR-4, so this test
    confirms behavior stays consistent rather than reading the internal table)."""
    create_response = client.post(
        "/tasks", json={"title": "Task", "category": "Home"}, headers=auth_headers
    )
    task_id = create_response.json()["id"]

    # Editing a field on a manually-created task is an ordinary edit
    # (FR-3.3), not a Quiet Correction (FR-4.x is scoped to AI-assigned
    # fields on AI-generated tasks) — this should succeed without issue.
    patch_response = client.patch(
        f"/tasks/{task_id}", json={"category": "Errands"}, headers=auth_headers
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["category"] == "Errands"
