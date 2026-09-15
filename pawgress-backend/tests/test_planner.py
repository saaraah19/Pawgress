"""
tests/test_planner.py — Weekly/Monthly Planner (2026-09-15).

Deliberately no test asserts anything about "did the user fill this in"
tracking, because no such tracking exists (planner/models.py's module
docstring) — what's tested instead: get-returns-null-not-404 for an unset
period, upsert creates-then-updates the same row rather than duplicating,
partial updates (setting only intention leaves reflection alone and vice
versa), period normalization (any date within a week/month resolves to
the same entry), and per-user scoping.
"""

import uuid


def test_get_unset_period_returns_null_not_404(client, auth_headers):
    """An unset period is a normal, expected state — never an error."""
    response = client.get("/planner", params={"periodType": "Week", "periodStart": "2026-09-14"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() is None


def test_planner_requires_auth(client):
    response = client.get("/planner", params={"periodType": "Week", "periodStart": "2026-09-14"})
    assert response.status_code == 403
    assert client.put("/planner", json={"periodType": "Week", "periodStart": "2026-09-14"}).status_code == 403


def test_upsert_creates_then_get_returns_it(client, auth_headers):
    upsert_response = client.put(
        "/planner",
        json={"periodType": "Week", "periodStart": "2026-09-14", "intention": "Ship the planner feature"},
        headers=auth_headers,
    )
    assert upsert_response.status_code == 200
    assert upsert_response.json()["intention"] == "Ship the planner feature"
    assert upsert_response.json()["reflection"] is None

    get_response = client.get("/planner", params={"periodType": "Week", "periodStart": "2026-09-14"}, headers=auth_headers)
    assert get_response.json()["intention"] == "Ship the planner feature"


def test_upsert_twice_updates_the_same_row_not_a_duplicate(client, auth_headers):
    client.put(
        "/planner", json={"periodType": "Week", "periodStart": "2026-09-14", "intention": "First draft"}, headers=auth_headers
    )
    second_response = client.put(
        "/planner", json={"periodType": "Week", "periodStart": "2026-09-14", "intention": "Revised"}, headers=auth_headers
    )
    assert second_response.json()["intention"] == "Revised"

    entry_id_first = second_response.json()["id"]
    third_response = client.put(
        "/planner", json={"periodType": "Week", "periodStart": "2026-09-14", "reflection": "Went well"}, headers=auth_headers
    )
    assert third_response.json()["id"] == entry_id_first
    assert third_response.json()["intention"] == "Revised"  # untouched by the reflection-only update
    assert third_response.json()["reflection"] == "Went well"


def test_omitting_a_field_leaves_it_unchanged(client, auth_headers):
    """exclude_unset semantics: a request that doesn't mention `reflection`
    at all must not reset it, same pattern as update_task/update_habit."""
    client.put(
        "/planner",
        json={"periodType": "Month", "periodStart": "2026-09-01", "intention": "Focus month", "reflection": "n/a yet"},
        headers=auth_headers,
    )
    response = client.put(
        "/planner", json={"periodType": "Month", "periodStart": "2026-09-01", "intention": "Focus month, revised"}, headers=auth_headers
    )
    assert response.json()["reflection"] == "n/a yet"


def test_week_period_start_normalizes_to_containing_sunday(client, auth_headers):
    """Any date inside the target week resolves to the same entry — the
    client never has to compute the exact Sunday itself, same convenience
    as habits/routes.py's weekStart param."""
    client.put(
        "/planner", json={"periodType": "Week", "periodStart": "2026-09-16", "intention": "Mid-week set"}, headers=auth_headers
    )
    # 2026-09-13 (Sun) through 2026-09-19 (Sat) are the same week.
    response = client.get("/planner", params={"periodType": "Week", "periodStart": "2026-09-13"}, headers=auth_headers)
    assert response.json()["intention"] == "Mid-week set"
    assert response.json()["periodStart"] == "2026-09-13"


def test_month_period_start_normalizes_to_the_first(client, auth_headers):
    client.put(
        "/planner", json={"periodType": "Month", "periodStart": "2026-09-20", "intention": "Mid-month set"}, headers=auth_headers
    )
    response = client.get("/planner", params={"periodType": "Month", "periodStart": "2026-09-01"}, headers=auth_headers)
    assert response.json()["intention"] == "Mid-month set"
    assert response.json()["periodStart"] == "2026-09-01"


def test_week_and_month_entries_for_the_same_calendar_range_are_independent(client, auth_headers):
    client.put(
        "/planner", json={"periodType": "Week", "periodStart": "2026-09-01", "intention": "Week intention"}, headers=auth_headers
    )
    client.put(
        "/planner", json={"periodType": "Month", "periodStart": "2026-09-01", "intention": "Month intention"}, headers=auth_headers
    )
    week_response = client.get("/planner", params={"periodType": "Week", "periodStart": "2026-09-01"}, headers=auth_headers)
    month_response = client.get("/planner", params={"periodType": "Month", "periodStart": "2026-09-01"}, headers=auth_headers)
    assert week_response.json()["intention"] == "Week intention"
    assert month_response.json()["intention"] == "Month intention"


def test_clearing_a_field_with_empty_string_sets_it_to_null(client, auth_headers):
    client.put(
        "/planner", json={"periodType": "Week", "periodStart": "2026-09-14", "intention": "Something"}, headers=auth_headers
    )
    response = client.put(
        "/planner", json={"periodType": "Week", "periodStart": "2026-09-14", "intention": ""}, headers=auth_headers
    )
    assert response.json()["intention"] is None


def test_entries_are_scoped_to_the_authenticated_user(client, auth_headers, second_user_headers):
    client.put(
        "/planner", json={"periodType": "Week", "periodStart": "2026-09-14", "intention": "Mine"}, headers=auth_headers
    )
    response = client.get(
        "/planner", params={"periodType": "Week", "periodStart": "2026-09-14"}, headers=second_user_headers
    )
    assert response.json() is None
