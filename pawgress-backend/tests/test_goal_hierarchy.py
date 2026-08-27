"""
tests/test_goal_hierarchy.py — V2 full goal hierarchy (Blueprint §13).

Covers: creating goals with/without a tier, assigning a tier and parent
after the fact via PATCH, the tier-ordering invariant (goal_service.
validate_parent_link), cross-user parent rejection (same pattern as
Domain Model Invariant 3 for Task->Goal), and that deleting a Goal unlinks
child Goals exactly as it already unlinks Tasks (Domain Model Invariant 9,
extended).
"""


def test_create_flat_goal_has_no_tier(client, auth_headers):
    """Omitting tier at creation must behave exactly like the old MVP flat
    goal — no forced hierarchy participation."""
    response = client.post("/goals", json={"label": "Someday maybe"}, headers=auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["tier"] is None
    assert body["parentGoalId"] is None


def test_create_goal_with_tier(client, auth_headers):
    response = client.post("/goals", json={"label": "2027", "tier": "Annual"}, headers=auth_headers)
    assert response.status_code == 201, response.text
    assert response.json()["tier"] == "Annual"


def test_assign_tier_after_creation_via_patch(client, auth_headers):
    """A user 'earning' hierarchy on an existing flat goal — tier is not
    forced at creation, but can be added later, one field at a time."""
    goal_id = client.post("/goals", json={"label": "Fitness"}, headers=auth_headers).json()["id"]
    response = client.patch(f"/goals/{goal_id}", json={"tier": "Project"}, headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["tier"] == "Project"


def test_link_valid_parent_child(client, auth_headers):
    annual_id = client.post("/goals", json={"label": "2027", "tier": "Annual"}, headers=auth_headers).json()["id"]
    project_id = client.post(
        "/goals", json={"label": "Launch the app", "tier": "Project"}, headers=auth_headers
    ).json()["id"]

    response = client.patch(f"/goals/{project_id}", json={"parentGoalId": annual_id}, headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["parentGoalId"] == annual_id


def test_project_can_skip_quarterly_and_attach_directly_to_annual(client, auth_headers):
    """Domain Model §4.3's 'earns hierarchy, doesn't assume it' — a user
    shouldn't be forced through every intermediate tier. Any strictly
    higher tier is a legal parent, not just the immediately adjacent one."""
    annual_id = client.post("/goals", json={"label": "2027", "tier": "Annual"}, headers=auth_headers).json()["id"]
    milestone_id = client.post(
        "/goals", json={"label": "First 100 users", "tier": "Milestone"}, headers=auth_headers
    ).json()["id"]

    response = client.patch(f"/goals/{milestone_id}", json={"parentGoalId": annual_id}, headers=auth_headers)
    assert response.status_code == 200, response.text


def test_reversed_tier_order_is_rejected(client, auth_headers):
    """A Milestone cannot be the parent of an Annual goal — the parent must
    be a strictly broader tier."""
    annual_id = client.post("/goals", json={"label": "2027", "tier": "Annual"}, headers=auth_headers).json()["id"]
    milestone_id = client.post(
        "/goals", json={"label": "First 100 users", "tier": "Milestone"}, headers=auth_headers
    ).json()["id"]

    response = client.patch(f"/goals/{annual_id}", json={"parentGoalId": milestone_id}, headers=auth_headers)
    assert response.status_code == 422


def test_same_tier_cannot_be_parent(client, auth_headers):
    """Strictly higher, not equal — two Project-tier goals can't nest under
    each other."""
    project_a = client.post("/goals", json={"label": "A", "tier": "Project"}, headers=auth_headers).json()["id"]
    project_b = client.post("/goals", json={"label": "B", "tier": "Project"}, headers=auth_headers).json()["id"]

    response = client.patch(f"/goals/{project_b}", json={"parentGoalId": project_a}, headers=auth_headers)
    assert response.status_code == 422


def test_untiered_goal_cannot_have_a_parent(client, auth_headers):
    """An untiered (flat) goal has no rank to compare — it must be given a
    tier before it can be nested."""
    annual_id = client.post("/goals", json={"label": "2027", "tier": "Annual"}, headers=auth_headers).json()["id"]
    flat_id = client.post("/goals", json={"label": "Just a note"}, headers=auth_headers).json()["id"]

    response = client.patch(f"/goals/{flat_id}", json={"parentGoalId": annual_id}, headers=auth_headers)
    assert response.status_code == 422


def test_untiered_goal_cannot_be_a_parent(client, auth_headers):
    flat_id = client.post("/goals", json={"label": "Just a note"}, headers=auth_headers).json()["id"]
    project_id = client.post("/goals", json={"label": "P", "tier": "Project"}, headers=auth_headers).json()["id"]

    response = client.patch(f"/goals/{project_id}", json={"parentGoalId": flat_id}, headers=auth_headers)
    assert response.status_code == 422


def test_goal_cannot_be_its_own_parent(client, auth_headers):
    goal_id = client.post("/goals", json={"label": "2027", "tier": "Annual"}, headers=auth_headers).json()["id"]
    response = client.patch(f"/goals/{goal_id}", json={"parentGoalId": goal_id}, headers=auth_headers)
    assert response.status_code == 422


def test_cannot_link_to_another_users_goal_as_parent(client, auth_headers, second_user_headers):
    """Same cross-user isolation already enforced for Task->Goal (Domain
    Model Invariant 3), now extended to Goal->Goal."""
    other_users_annual = client.post(
        "/goals", json={"label": "Not yours", "tier": "Annual"}, headers=second_user_headers
    ).json()["id"]
    my_project = client.post("/goals", json={"label": "Mine", "tier": "Project"}, headers=auth_headers).json()["id"]

    response = client.patch(
        f"/goals/{my_project}", json={"parentGoalId": other_users_annual}, headers=auth_headers
    )
    assert response.status_code == 404


def test_clear_parent_with_explicit_null(client, auth_headers):
    annual_id = client.post("/goals", json={"label": "2027", "tier": "Annual"}, headers=auth_headers).json()["id"]
    project_id = client.post("/goals", json={"label": "P", "tier": "Project"}, headers=auth_headers).json()["id"]
    client.patch(f"/goals/{project_id}", json={"parentGoalId": annual_id}, headers=auth_headers)

    response = client.patch(f"/goals/{project_id}", json={"parentGoalId": None}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["parentGoalId"] is None


def test_deleting_a_parent_goal_unlinks_but_does_not_delete_children(client, auth_headers):
    """Direct extension of Domain Model Invariant 9 to the new parent/child
    relationship — the exact behavior goal_service.py's
    delete_goal_and_unlink_references exists to guarantee."""
    annual_id = client.post("/goals", json={"label": "2027", "tier": "Annual"}, headers=auth_headers).json()["id"]
    project_id = client.post("/goals", json={"label": "P", "tier": "Project"}, headers=auth_headers).json()["id"]
    client.patch(f"/goals/{project_id}", json={"parentGoalId": annual_id}, headers=auth_headers)

    delete_response = client.delete(f"/goals/{annual_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    goals = {g["id"]: g for g in client.get("/goals", headers=auth_headers).json()}
    assert project_id in goals  # child survives
    assert goals[project_id]["parentGoalId"] is None  # but is unlinked
    assert annual_id not in goals  # parent is actually gone


def test_deleting_a_goal_still_unlinks_linked_tasks(client, auth_headers):
    """Regression guard — the extended delete function must not have
    dropped the original Task-unlinking behavior it's built on top of."""
    goal_id = client.post("/goals", json={"label": "Move house"}, headers=auth_headers).json()["id"]
    task_id = client.post("/tasks", json={"title": "Pack boxes"}, headers=auth_headers).json()["id"]
    client.patch(f"/tasks/{task_id}", json={"goalId": goal_id}, headers=auth_headers)

    client.delete(f"/goals/{goal_id}", headers=auth_headers)

    tasks = {t["id"]: t for t in client.get("/tasks", headers=auth_headers).json()}
    assert tasks[task_id]["goalId"] is None


def test_update_goal_label(client, auth_headers):
    """One-tap-correction shape (FR-4.x's pattern, extended to Goal) —
    a single field can be changed without confirmation."""
    goal_id = client.post("/goals", json={"label": "Old label"}, headers=auth_headers).json()["id"]
    response = client.patch(f"/goals/{goal_id}", json={"label": "New label"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["label"] == "New label"


def test_update_nonexistent_goal_returns_404(client, auth_headers):
    response = client.patch(
        "/goals/00000000-0000-0000-0000-000000000000", json={"label": "x"}, headers=auth_headers
    )
    assert response.status_code == 404


def test_cannot_update_another_users_goal(client, auth_headers, second_user_headers):
    goal_id = client.post("/goals", json={"label": "Mine"}, headers=auth_headers).json()["id"]
    response = client.patch(f"/goals/{goal_id}", json={"label": "Hijacked"}, headers=second_user_headers)
    assert response.status_code == 404


def test_changing_tier_alone_that_breaks_existing_parent_link_is_rejected(client, auth_headers):
    """The real edge case: re-tiering a goal without touching parentGoalId
    can silently invalidate its existing parent relationship if left
    unchecked. Milestone -> Annual under an Annual parent would leave
    parent.tier == child.tier, violating 'parent must be strictly
    broader.' Must be rejected outright, not silently applied or silently
    unlinked."""
    annual_id = client.post("/goals", json={"label": "2027", "tier": "Annual"}, headers=auth_headers).json()["id"]
    milestone_id = client.post(
        "/goals", json={"label": "First 100 users", "tier": "Milestone"}, headers=auth_headers
    ).json()["id"]
    client.patch(f"/goals/{milestone_id}", json={"parentGoalId": annual_id}, headers=auth_headers)

    response = client.patch(f"/goals/{milestone_id}", json={"tier": "Annual"}, headers=auth_headers)
    assert response.status_code == 422

    # And nothing was actually changed by the rejected request.
    goals = {g["id"]: g for g in client.get("/goals", headers=auth_headers).json()}
    assert goals[milestone_id]["tier"] == "Milestone"
    assert goals[milestone_id]["parentGoalId"] == annual_id


def test_changing_tier_alone_that_breaks_an_existing_child_link_is_rejected(client, auth_headers):
    """Same edge case from the parent's side: re-tiering a goal that
    currently has children can invalidate one of those child links."""
    annual_id = client.post("/goals", json={"label": "2027", "tier": "Annual"}, headers=auth_headers).json()["id"]
    project_id = client.post("/goals", json={"label": "Launch", "tier": "Project"}, headers=auth_headers).json()["id"]
    client.patch(f"/goals/{project_id}", json={"parentGoalId": annual_id}, headers=auth_headers)

    # Annual -> Milestone would make it a narrower tier than its Project child.
    response = client.patch(f"/goals/{annual_id}", json={"tier": "Milestone"}, headers=auth_headers)
    assert response.status_code == 422

    goals = {g["id"]: g for g in client.get("/goals", headers=auth_headers).json()}
    assert goals[annual_id]["tier"] == "Annual"
    assert goals[project_id]["parentGoalId"] == annual_id


def test_changing_tier_that_stays_consistent_with_existing_links_succeeds(client, auth_headers):
    """Negative-case sibling to the two tests above — a tier change that
    stays valid for all existing edges must not be blocked by the
    re-validation logic."""
    annual_id = client.post("/goals", json={"label": "2027", "tier": "Annual"}, headers=auth_headers).json()["id"]
    milestone_id = client.post(
        "/goals", json={"label": "First 100 users", "tier": "Milestone"}, headers=auth_headers
    ).json()["id"]
    client.patch(f"/goals/{milestone_id}", json={"parentGoalId": annual_id}, headers=auth_headers)

    # Milestone -> Project is still strictly narrower than the Annual parent.
    response = client.patch(f"/goals/{milestone_id}", json={"tier": "Project"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["tier"] == "Project"
    assert response.json()["parentGoalId"] == annual_id
