"""
tests/test_goals.py — FR-5.1 (goal creation), FR-5.2 (task-to-goal linking),
Domain Model Invariant 3 (cross-user linking invalid), Invariant 9 /
§10.5 GoalDeletionService (unlink, never cascade).
"""


def test_create_and_list_goals(client, auth_headers):
    response = client.post("/goals", json={"label": "Learn guitar"}, headers=auth_headers)
    assert response.status_code == 201, response.text
    assert response.json()["label"] == "Learn guitar"

    list_response = client.get("/goals", headers=auth_headers)
    labels = [g["label"] for g in list_response.json()]
    assert "Learn guitar" in labels


def test_create_goal_requires_label(client, auth_headers):
    response = client.post("/goals", json={"label": ""}, headers=auth_headers)
    assert response.status_code == 422


def test_link_task_to_goal(client, auth_headers):
    goal_id = client.post("/goals", json={"label": "Fitness"}, headers=auth_headers).json()["id"]
    task_id = client.post("/tasks", json={"title": "Go for a run"}, headers=auth_headers).json()["id"]

    response = client.patch(f"/tasks/{task_id}", json={"goalId": goal_id}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["goalId"] == goal_id


def test_unlink_task_from_goal_with_explicit_null(client, auth_headers):
    """FR-5.2 — linking is fully optional and reversible. Sending an
    explicit `goalId: null` clears the link (distinct from omitting the
    field entirely, which must leave it untouched)."""
    goal_id = client.post("/goals", json={"label": "Fitness"}, headers=auth_headers).json()["id"]
    task_id = client.post("/tasks", json={"title": "Go for a run"}, headers=auth_headers).json()["id"]
    client.patch(f"/tasks/{task_id}", json={"goalId": goal_id}, headers=auth_headers)

    response = client.patch(f"/tasks/{task_id}", json={"goalId": None}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["goalId"] is None


def test_omitted_goal_id_leaves_link_untouched(client, auth_headers):
    goal_id = client.post("/goals", json={"label": "Fitness"}, headers=auth_headers).json()["id"]
    task_id = client.post("/tasks", json={"title": "Go for a run"}, headers=auth_headers).json()["id"]
    client.patch(f"/tasks/{task_id}", json={"goalId": goal_id}, headers=auth_headers)

    # Correcting an unrelated field must not disturb the existing goal link.
    response = client.patch(f"/tasks/{task_id}", json={"priority": "High"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["goalId"] == goal_id


def test_cannot_link_task_to_another_users_goal(client, auth_headers, second_user_headers):
    """Domain Model Invariant 3: cross-user linking is invalid under any
    circumstance — must fail, not silently succeed or silently no-op."""
    other_users_goal_id = client.post(
        "/goals", json={"label": "Not yours"}, headers=second_user_headers
    ).json()["id"]
    task_id = client.post("/tasks", json={"title": "My task"}, headers=auth_headers).json()["id"]

    response = client.patch(
        f"/tasks/{task_id}", json={"goalId": other_users_goal_id}, headers=auth_headers
    )
    assert response.status_code == 404


def test_deleting_goal_unlinks_but_does_not_delete_linked_tasks(client, auth_headers):
    """Invariant 9 / §10.5 GoalDeletionService — the exact behavior this
    slice's goal_service.py exists to guarantee."""
    goal_id = client.post("/goals", json={"label": "Move house"}, headers=auth_headers).json()["id"]
    task_id = client.post("/tasks", json={"title": "Pack boxes"}, headers=auth_headers).json()["id"]
    client.patch(f"/tasks/{task_id}", json={"goalId": goal_id}, headers=auth_headers)

    delete_response = client.delete(f"/goals/{goal_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    # Task still exists...
    list_response = client.get("/tasks", headers=auth_headers)
    tasks = {t["id"]: t for t in list_response.json()}
    assert task_id in tasks
    # ...but is now unlinked, not still pointing at a deleted goal.
    assert tasks[task_id]["goalId"] is None

    # And the goal itself is gone.
    goals_response = client.get("/goals", headers=auth_headers)
    goal_ids = [g["id"] for g in goals_response.json()]
    assert goal_id not in goal_ids


def test_cannot_delete_another_users_goal(client, auth_headers, second_user_headers):
    goal_id = client.post("/goals", json={"label": "Mine"}, headers=auth_headers).json()["id"]
    response = client.delete(f"/goals/{goal_id}", headers=second_user_headers)
    assert response.status_code == 404
