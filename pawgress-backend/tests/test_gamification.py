"""
tests/test_gamification.py — XP/Level (2026-09-16). Nothing here is
persisted (gamification/catalog.py's docstring) — every test works by
creating real Task/Habit completions and checking the computed state,
never by manipulating a gamification-specific table (there isn't one).
"""

import uuid


def test_gamification_requires_auth(client):
    assert client.get("/gamification/state").status_code == 403


def test_new_user_starts_at_level_1_zero_xp(client, auth_headers):
    response = client.get("/gamification/state", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["level"] == 1
    assert body["xp"] == 0
    assert body["completions"] == 0


def test_task_completion_counts_toward_xp(client, auth_headers):
    task_id = client.post("/tasks", json={"title": "Do the thing"}, headers=auth_headers).json()["id"]
    client.patch(f"/tasks/{task_id}", json={"status": "Done"}, headers=auth_headers)

    response = client.get("/gamification/state", headers=auth_headers)
    body = response.json()
    assert body["completions"] == 1
    assert body["xp"] == 1


def test_habit_completion_counts_toward_xp(client, auth_headers):
    habit_id = client.post("/habits", json={"label": "Stretch", "frequency": "Daily"}, headers=auth_headers).json()["id"]
    client.post(f"/habits/{habit_id}/completions", headers=auth_headers)

    response = client.get("/gamification/state", headers=auth_headers)
    body = response.json()
    assert body["completions"] == 1
    assert body["xp"] == 1


def test_undoing_a_completion_removes_its_xp(client, auth_headers):
    """XP only ever accumulates while the underlying completions exist —
    but it's honestly recomputed, not a one-way ratchet independent of
    reality: undoing a genuine mistake (not a 'penalty') removes the XP
    that came from it, same as it removes the mood signal (see
    test_companion.py's equivalent test for Task completion)."""
    task_id = client.post("/tasks", json={"title": "Oops"}, headers=auth_headers).json()["id"]
    client.patch(f"/tasks/{task_id}", json={"status": "Done"}, headers=auth_headers)
    client.patch(f"/tasks/{task_id}", json={"status": "NotStarted"}, headers=auth_headers)

    response = client.get("/gamification/state", headers=auth_headers)
    assert response.json()["xp"] == 0


def test_reaching_level_2_unlocks_the_first_badge(client, auth_headers):
    """Level 2 requires 10 XP (xp_for_level(2) == 10) — create and
    complete 10 tasks."""
    for i in range(10):
        task_id = client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_headers).json()["id"]
        client.patch(f"/tasks/{task_id}", json={"status": "Done"}, headers=auth_headers)

    response = client.get("/gamification/state", headers=auth_headers)
    body = response.json()
    assert body["level"] == 2
    first_badge = next(item for item in body["items"] if item["id"] == "badge-first-steps")
    assert first_badge["unlocked"] is True
    # A level-3 item must still be locked.
    terracotta = next(item for item in body["items"] if item["id"] == "theme-terracotta")
    assert terracotta["unlocked"] is False


def test_level_1_default_theme_is_always_unlocked(client, auth_headers):
    response = client.get("/gamification/state", headers=auth_headers)
    sage = next(item for item in response.json()["items"] if item["id"] == "theme-sage")
    assert sage["unlocked"] is True


def test_gamification_state_is_scoped_to_the_authenticated_user(client, auth_headers, second_user_headers):
    task_id = client.post("/tasks", json={"title": "Mine"}, headers=auth_headers).json()["id"]
    client.patch(f"/tasks/{task_id}", json={"status": "Done"}, headers=auth_headers)

    other_response = client.get("/gamification/state", headers=second_user_headers)
    assert other_response.json()["xp"] == 0


def test_deleting_a_habit_removes_its_completions_xp_too(client, auth_headers):
    """habit_completions cascades on habit deletion (ondelete=CASCADE) —
    confirms gamification state reflects that honestly rather than
    counting phantom completions for a habit that no longer exists."""
    habit_id = client.post("/habits", json={"label": "Temp", "frequency": "Daily"}, headers=auth_headers).json()["id"]
    client.post(f"/habits/{habit_id}/completions", headers=auth_headers)
    assert client.get("/gamification/state", headers=auth_headers).json()["xp"] == 1

    client.delete(f"/habits/{habit_id}", headers=auth_headers)
    assert client.get("/gamification/state", headers=auth_headers).json()["xp"] == 0
