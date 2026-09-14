"""
tests/test_security.py — pre-deployment security pass (2026-09-13):
login/register rate limiting, and the password-reset token flow.
"""

import uuid

from shared.rate_limit import login_rate_limiter, register_rate_limiter, password_reset_rate_limiter


def test_register_is_rate_limited_after_max_attempts(client):
    for _ in range(register_rate_limiter.max_attempts):
        client.post(
            "/auth/register",
            json={"email": f"user_{uuid.uuid4().hex[:8]}@example.com", "password": "correct-horse-battery"},
        )

    response = client.post(
        "/auth/register", json={"email": f"user_{uuid.uuid4().hex[:8]}@example.com", "password": "correct-horse-battery"}
    )
    assert response.status_code == 429


def test_login_is_rate_limited_after_max_attempts(client):
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})

    for _ in range(login_rate_limiter.max_attempts):
        client.post("/auth/login", json={"email": email, "password": "wrong-password"})

    response = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert response.status_code == 429


def test_password_reset_flow_end_to_end(client, monkeypatch):
    """The full round trip: request a reset, capture the token the way a
    real email would have delivered it (here, monkeypatching the send
    function since no real provider is wired up — see
    identity/password_reset.py), confirm with a new password, then log in
    with the NEW password successfully and the OLD one no longer works."""
    captured = {}

    def fake_send(email, token):
        captured["token"] = token

    import identity.routes as routes_module

    monkeypatch.setattr(routes_module, "send_password_reset_email", fake_send)

    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={"email": email, "password": "original-password"})

    request_response = client.post("/auth/password-reset/request", json={"email": email})
    assert request_response.status_code == 202
    assert "token" in captured

    confirm_response = client.post(
        "/auth/password-reset/confirm", json={"token": captured["token"], "new_password": "brand-new-password"}
    )
    assert confirm_response.status_code == 204

    old_password_response = client.post("/auth/login", json={"email": email, "password": "original-password"})
    assert old_password_response.status_code == 401

    new_password_response = client.post("/auth/login", json={"email": email, "password": "brand-new-password"})
    assert new_password_response.status_code == 200


def test_password_reset_request_for_unknown_email_still_returns_202(client):
    """Never leak whether an email is registered — same posture as
    login's unified error message."""
    response = client.post(
        "/auth/password-reset/request", json={"email": f"nobody_{uuid.uuid4().hex[:8]}@example.com"}
    )
    assert response.status_code == 202


def test_password_reset_confirm_rejects_garbage_token(client):
    response = client.post(
        "/auth/password-reset/confirm", json={"token": "not-a-real-token", "new_password": "whatever12345"}
    )
    assert response.status_code == 400


def test_password_reset_confirm_rejects_an_access_token(client, auth_headers):
    """The `purpose` claim check: a perfectly valid, unexpired access
    token must NOT be usable as a password-reset token, even though both
    are signed with the same secret."""
    access_token = auth_headers["Authorization"].split(" ")[1]

    response = client.post(
        "/auth/password-reset/confirm", json={"token": access_token, "new_password": "whatever12345"}
    )
    assert response.status_code == 400


def test_password_reset_is_rate_limited(client):
    for _ in range(password_reset_rate_limiter.max_attempts):
        client.post("/auth/password-reset/request", json={"email": f"nobody_{uuid.uuid4().hex[:8]}@example.com"})

    response = client.post(
        "/auth/password-reset/request", json={"email": f"nobody_{uuid.uuid4().hex[:8]}@example.com"}
    )
    assert response.status_code == 429
