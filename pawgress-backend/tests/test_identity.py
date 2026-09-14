"""
tests/test_identity.py — FR-1.1 (account creation), FR-1.2 (session
persistence), FR-1.3 (minimal profile).

This module had zero dedicated test coverage before this file — every
other endpoint in the app depends on register/login working (via the
`auth_headers` fixture), but nothing exercised the endpoints' own error
paths or contract directly. Given this is the literal front door of the
product, that gap mattered more than most.
"""

import uuid


def test_register_creates_account_and_returns_token(client):
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    response = client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    assert response.status_code == 201
    body = response.json()
    assert "access_token" in body and body["access_token"]
    assert "user_id" in body


def test_register_duplicate_email_is_rejected_with_plain_message(client):
    """AC-1.1.2: a non-judgmental, plain-language error — not a raw
    technical/DB error — per Brand §6 applied to system errors."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})

    response = client.post("/auth/register", json={"email": email, "password": "another-password"})
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


def test_register_rejects_short_password(client):
    """RegisterRequest's minimum_length validator — AC-1.1.1's 'meeting
    minimum security requirements' clause."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    response = client.post("/auth/register", json={"email": email, "password": "short"})
    assert response.status_code == 422


def test_register_rejects_malformed_email(client):
    response = client.post("/auth/register", json={"email": "not-an-email", "password": "correct-horse-battery"})
    assert response.status_code == 422


def test_new_account_has_no_forced_setup_and_neutral_display_name(client):
    """BR-1: no onboarding step required. FR-1.3/AC-1.3.1: a new account
    with no display name shows the neutral placeholder, not a forced
    field or an empty string."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    register_response = client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    token = register_response.json()["access_token"]

    profile_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert profile_response.status_code == 200
    body = profile_response.json()
    assert body["display_name"] == "Friend"
    assert body["email"] == email


def test_login_with_correct_credentials_succeeds(client):
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})

    response = client.post("/auth/login", json={"email": email, "password": "correct-horse-battery"})
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_with_wrong_password_is_rejected(client):
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})

    response = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert response.status_code == 401


def test_login_with_unknown_email_is_rejected_identically_to_wrong_password(client):
    """Deliberately the same error/status for 'no such account' and 'wrong
    password' — distinguishing them would leak which emails are
    registered, a real (if small) privacy/security leak most apps get
    wrong by accident."""
    unknown_response = client.post(
        "/auth/login", json={"email": f"nobody_{uuid.uuid4().hex[:8]}@example.com", "password": "whatever123"}
    )

    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    wrong_password_response = client.post("/auth/login", json={"email": email, "password": "wrong-password"})

    assert unknown_response.status_code == wrong_password_response.status_code == 401
    assert unknown_response.json()["detail"] == wrong_password_response.json()["detail"]


def test_protected_endpoint_without_token_is_rejected(client):
    response = client.get("/auth/me")
    assert response.status_code == 403  # HTTPBearer's own default for a missing Authorization header


def test_protected_endpoint_with_garbage_token_is_rejected(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_protected_endpoint_with_expired_token_is_rejected(client, session_factory):
    """get_current_user's jwt.decode call enforces `exp` itself (python-jose
    raises JWTError on an expired token) — this confirms that enforcement
    actually fires, not just that the code path exists."""
    from datetime import datetime, timedelta, timezone
    from jose import jwt as jose_jwt
    from shared.config import settings
    from identity.models import User

    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    register_response = client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    user_id = register_response.json()["user_id"]

    expired_payload = {"sub": user_id, "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}
    expired_token = jose_jwt.encode(expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


def test_token_for_deleted_user_is_rejected(client, session_factory):
    """get_current_user's final DB lookup: a structurally valid, unexpired
    token for a user who no longer exists must still be rejected, not
    silently treated as valid."""
    from identity.models import User

    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    register_response = client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    token = register_response.json()["access_token"]
    user_id = register_response.json()["user_id"]

    db = session_factory()
    try:
        db.query(User).filter(User.id == user_id).delete()
        db.commit()
    finally:
        db.close()

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_password_is_never_returned_in_any_response(client):
    """Not a specific FR, but a baseline any auth system should meet —
    worth a direct assertion rather than an implicit assumption."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    register_response = client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    assert "password" not in register_response.text.lower()

    token = register_response.json()["access_token"]
    profile_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert "password" not in profile_response.text.lower()
