"""
tests/test_journal.py — Journal module (Domain Model §13, Blueprint V2 §13).

Covers basic CRUD, cross-user isolation (same pattern as every other
module), and confirms this module never touches ai_extraction — journaling
and task-extraction are different intents, per Domain Model §13, and that
separation should hold structurally, not just by convention.
"""


def test_create_journal_entry(client, auth_headers):
    response = client.post("/journal", json={"text": "Today was a quiet day."}, headers=auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["text"] == "Today was a quiet day."
    assert body["id"]
    assert body["createdAt"]
    assert body["updatedAt"]


def test_create_requires_nonempty_text(client, auth_headers):
    response = client.post("/journal", json={"text": ""}, headers=auth_headers)
    assert response.status_code == 422


def test_create_requires_auth(client):
    response = client.post("/journal", json={"text": "x"})
    assert response.status_code == 403


def test_list_entries_newest_first(client, auth_headers):
    client.post("/journal", json={"text": "first"}, headers=auth_headers)
    client.post("/journal", json={"text": "second"}, headers=auth_headers)

    response = client.get("/journal", headers=auth_headers)
    assert response.status_code == 200
    texts = [e["text"] for e in response.json()]
    assert texts[:2] == ["second", "first"]


def test_list_scoped_to_authenticated_user(client, auth_headers, second_user_headers):
    client.post("/journal", json={"text": "mine"}, headers=auth_headers)
    client.post("/journal", json={"text": "not mine"}, headers=second_user_headers)

    my_entries = client.get("/journal", headers=auth_headers).json()
    texts = [e["text"] for e in my_entries]
    assert "mine" in texts
    assert "not mine" not in texts


def test_update_entry_text(client, auth_headers):
    """Journal entries are editable by design (unlike Capture's immutable
    raw text) — see journal/models.py's docstring for why."""
    entry_id = client.post("/journal", json={"text": "typo verison"}, headers=auth_headers).json()["id"]
    response = client.patch(f"/journal/{entry_id}", json={"text": "typo version"}, headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["text"] == "typo version"


def test_update_nonexistent_entry_returns_404(client, auth_headers):
    response = client.patch(
        "/journal/00000000-0000-0000-0000-000000000000", json={"text": "x"}, headers=auth_headers
    )
    assert response.status_code == 404


def test_cannot_update_another_users_entry(client, auth_headers, second_user_headers):
    entry_id = client.post("/journal", json={"text": "mine"}, headers=auth_headers).json()["id"]
    response = client.patch(f"/journal/{entry_id}", json={"text": "hijacked"}, headers=second_user_headers)
    assert response.status_code == 404


def test_delete_entry(client, auth_headers):
    entry_id = client.post("/journal", json={"text": "delete me"}, headers=auth_headers).json()["id"]
    delete_response = client.delete(f"/journal/{entry_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    remaining_ids = [e["id"] for e in client.get("/journal", headers=auth_headers).json()]
    assert entry_id not in remaining_ids


def test_cannot_delete_another_users_entry(client, auth_headers, second_user_headers):
    entry_id = client.post("/journal", json={"text": "mine"}, headers=auth_headers).json()["id"]
    response = client.delete(f"/journal/{entry_id}", headers=second_user_headers)
    assert response.status_code == 404

    remaining_ids = [e["id"] for e in client.get("/journal", headers=auth_headers).json()]
    assert entry_id in remaining_ids


def test_journal_module_has_no_ai_extraction_dependency():
    """Structural guard, not just convention: Domain Model §13 says
    journaling and task-extraction are different intents. Confirms
    journal/routes.py never *imports* ai_extraction, so no future edit can
    silently wire an extraction call into this surface. Uses AST parsing
    rather than a naive substring search, since the module's own docstring
    legitimately mentions "ai_extraction" by name to explain this exact
    guarantee — a plain text search would trip over its own documentation."""
    import ast
    import inspect
    import journal.routes as journal_routes

    tree = ast.parse(inspect.getsource(journal_routes))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])

    assert "ai_extraction" not in imported_modules
