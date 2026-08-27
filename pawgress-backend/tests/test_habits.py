"""
tests/test_habits.py — V2 Habits (Blueprint §13, §16).

Deliberately does NOT test for any "streak" or "missed day" concept,
because none exists in this design — see habits/models.py's module
docstring. What's tested instead: the accumulating-total progress signal,
frequency/weeklyTarget consistency (both at creation and on partial
update, mirroring the discipline already established for Goal hierarchy),
idempotent completion marking, and that deleting a Habit cascades to its
completions (the one deliberate cascade-delete exception in this codebase).
"""


def test_create_daily_habit(client, auth_headers):
    response = client.post("/habits", json={"label": "Stretch", "frequency": "Daily"}, headers=auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["frequency"] == "Daily"
    assert body["weeklyTarget"] is None
    assert body["totalCompletions"] == 0
    assert body["completedToday"] is False


def test_create_weekly_count_habit_requires_target(client, auth_headers):
    response = client.post("/habits", json={"label": "Gym", "frequency": "WeeklyCount"}, headers=auth_headers)
    assert response.status_code == 422


def test_create_weekly_count_habit_with_target(client, auth_headers):
    response = client.post(
        "/habits", json={"label": "Gym", "frequency": "WeeklyCount", "weeklyTarget": 3}, headers=auth_headers
    )
    assert response.status_code == 201, response.text
    assert response.json()["weeklyTarget"] == 3


def test_daily_habit_rejects_weekly_target(client, auth_headers):
    response = client.post(
        "/habits", json={"label": "Stretch", "frequency": "Daily", "weeklyTarget": 3}, headers=auth_headers
    )
    assert response.status_code == 422


def test_mark_habit_complete_increments_total(client, auth_headers):
    habit_id = client.post("/habits", json={"label": "Read", "frequency": "Daily"}, headers=auth_headers).json()["id"]
    response = client.post(f"/habits/{habit_id}/completions", headers=auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["totalCompletions"] == 1
    assert body["completedToday"] is True


def test_marking_complete_twice_same_day_is_idempotent(client, auth_headers):
    """A double-tap shouldn't inflate the count — completedToday is
    binary, matching Task's exactly-two-states precedent applied to a day."""
    habit_id = client.post("/habits", json={"label": "Read", "frequency": "Daily"}, headers=auth_headers).json()["id"]
    client.post(f"/habits/{habit_id}/completions", headers=auth_headers)
    response = client.post(f"/habits/{habit_id}/completions", headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["totalCompletions"] == 1


def test_undo_completion(client, auth_headers):
    """Removes a positive record — does not create a 'missed' record of
    any kind, because no such concept exists in this schema."""
    habit_id = client.post("/habits", json={"label": "Read", "frequency": "Daily"}, headers=auth_headers).json()["id"]
    client.post(f"/habits/{habit_id}/completions", headers=auth_headers)

    from datetime import date
    today = date.today().isoformat()
    response = client.delete(f"/habits/{habit_id}/completions/{today}", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["totalCompletions"] == 0
    assert response.json()["completedToday"] is False


def test_total_completions_accumulates_and_never_resets_via_backdated_entries(client, auth_headers):
    """Simulates several days of completions via explicit backdated
    entries (since the API allows specifying a date) — confirms the
    progress signal is a plain running total, not anything that could be
    reset or broken by a gap between them."""
    habit_id = client.post("/habits", json={"label": "Journal", "frequency": "Daily"}, headers=auth_headers).json()["id"]

    for d in ["2026-08-01", "2026-08-03", "2026-08-10"]:  # deliberately non-consecutive
        response = client.post(f"/habits/{habit_id}/completions?completion_date={d}", headers=auth_headers)
        assert response.status_code == 201

    listed = client.get("/habits", headers=auth_headers).json()
    habit = next(h for h in listed if h["id"] == habit_id)
    assert habit["totalCompletions"] == 3


def test_update_habit_label(client, auth_headers):
    habit_id = client.post("/habits", json={"label": "Old", "frequency": "Daily"}, headers=auth_headers).json()["id"]
    response = client.patch(f"/habits/{habit_id}", json={"label": "New"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["label"] == "New"


def test_changing_frequency_alone_that_conflicts_with_existing_target_is_rejected(client, auth_headers):
    """Same discipline as Goal hierarchy's tier-change re-validation:
    changing frequency to Daily while an existing weeklyTarget is still
    set must be rejected outright, not silently auto-cleared."""
    habit_id = client.post(
        "/habits", json={"label": "Gym", "frequency": "WeeklyCount", "weeklyTarget": 3}, headers=auth_headers
    ).json()["id"]

    response = client.patch(f"/habits/{habit_id}", json={"frequency": "Daily"}, headers=auth_headers)
    assert response.status_code == 422

    # Confirm nothing was actually changed by the rejected request.
    listed = client.get("/habits", headers=auth_headers).json()
    habit = next(h for h in listed if h["id"] == habit_id)
    assert habit["frequency"] == "WeeklyCount"
    assert habit["weeklyTarget"] == 3


def test_changing_frequency_and_clearing_target_together_succeeds(client, auth_headers):
    habit_id = client.post(
        "/habits", json={"label": "Gym", "frequency": "WeeklyCount", "weeklyTarget": 3}, headers=auth_headers
    ).json()["id"]

    response = client.patch(
        f"/habits/{habit_id}", json={"frequency": "Daily", "weeklyTarget": None}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["frequency"] == "Daily"
    assert response.json()["weeklyTarget"] is None


def test_link_habit_to_goal(client, auth_headers):
    goal_id = client.post("/goals", json={"label": "Get fit"}, headers=auth_headers).json()["id"]
    response = client.post(
        "/habits", json={"label": "Gym", "frequency": "Daily", "goalId": goal_id}, headers=auth_headers
    )
    assert response.status_code == 201, response.text
    assert response.json()["goalId"] == goal_id


def test_cannot_link_habit_to_another_users_goal(client, auth_headers, second_user_headers):
    other_goal_id = client.post("/goals", json={"label": "Not yours"}, headers=second_user_headers).json()["id"]
    response = client.post(
        "/habits", json={"label": "Gym", "frequency": "Daily", "goalId": other_goal_id}, headers=auth_headers
    )
    assert response.status_code == 404


def test_delete_habit_cascades_to_completions(client, auth_headers, session_factory):
    """The one deliberate cascade-delete exception in this codebase —
    verified directly against the DB, not just via the API, since the API
    alone can't prove the completion rows are actually gone versus merely
    unreachable."""
    habit_id = client.post("/habits", json={"label": "Read", "frequency": "Daily"}, headers=auth_headers).json()["id"]
    client.post(f"/habits/{habit_id}/completions", headers=auth_headers)

    delete_response = client.delete(f"/habits/{habit_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    from habits.models import HabitCompletion
    import uuid as uuid_mod

    db = session_factory()
    try:
        remaining = db.query(HabitCompletion).filter(HabitCompletion.habit_id == uuid_mod.UUID(habit_id)).count()
        assert remaining == 0
    finally:
        db.close()


def test_cannot_access_another_users_habit(client, auth_headers, second_user_headers):
    habit_id = client.post("/habits", json={"label": "Mine", "frequency": "Daily"}, headers=auth_headers).json()["id"]

    assert client.patch(f"/habits/{habit_id}", json={"label": "Hijacked"}, headers=second_user_headers).status_code == 404
    assert client.delete(f"/habits/{habit_id}", headers=second_user_headers).status_code == 404
    assert client.post(f"/habits/{habit_id}/completions", headers=second_user_headers).status_code == 404


def test_habits_requires_auth(client):
    assert client.get("/habits").status_code == 403
    assert client.post("/habits", json={"label": "x", "frequency": "Daily"}).status_code == 403
