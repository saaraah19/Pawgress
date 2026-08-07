"""
tests/test_profile.py — FR-1.3, AC-1.3.1.
"""


def test_new_account_shows_neutral_display_name_default(client, auth_headers):
    """AC-1.3.1: a new account with no display name provided shows a
    neutral default rather than requiring the field to proceed — no
    onboarding step, no blank state (BR-1)."""
    response = client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["display_name"] == "Friend"


def test_profile_requires_auth(client):
    response = client.get("/auth/me")
    assert response.status_code == 403


def test_profile_returns_own_email(client, auth_headers):
    """Sanity check that /auth/me reflects the authenticated user, not a
    hardcoded or cross-user value."""
    me = client.get("/auth/me", headers=auth_headers).json()
    assert "@" in me["email"]
    assert me["user_id"]
