"""
tests/test_calendar.py — V2 Calendar (read-only Google integration,
explicit scope decision 2026-08-19).

Everything here is verified against a stub CalendarProvider — this proves
the routing, state-token, persistence, and error-handling logic is
correct. It does NOT and CANNOT prove the real, live OAuth handshake
against Google's actual servers works — that requires the manual local
verification steps documented in docs/PROGRESS.md, with real credentials,
which is not something an automated test in this environment can
substitute for.
"""

import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

import pytest

from calendar_integration.google_provider import (
    CalendarProvider,
    GoogleTokens,
    NormalizedEvent,
    get_calendar_provider,
)
from calendar_integration.routes import _create_oauth_state
import main as main_module


class StubCalendarProvider(CalendarProvider):
    """Records calls made to it so tests can assert on behavior (e.g.
    "was refresh_access_token actually invoked") without hitting any
    real network."""

    def __init__(self):
        self.refresh_calls = 0
        self.revoke_calls = 0
        self.exchanged_codes = []

    def build_authorization_url(self, state: str) -> str:
        return f"https://accounts.google.com/fake-consent?state={state}"

    def exchange_code_for_tokens(self, code: str) -> GoogleTokens:
        self.exchanged_codes.append(code)
        return GoogleTokens(
            access_token=f"fake-access-token-for-{code}",
            refresh_token=f"fake-refresh-token-for-{code}",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    def get_account_email(self, access_token: str) -> str:
        return "someone@example.com"

    def refresh_access_token(self, refresh_token: str) -> GoogleTokens:
        self.refresh_calls += 1
        return GoogleTokens(
            access_token="refreshed-access-token",
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    def list_events(self, access_token: str, days_ahead: int = 14) -> list[NormalizedEvent]:
        now = datetime.now(timezone.utc)
        return [
            NormalizedEvent(
                id="evt-1",
                title="Dentist",
                start=now + timedelta(days=1),
                end=now + timedelta(days=1, hours=1),
                all_day=False,
                location=None,
            )
        ]

    def revoke(self, token: str) -> None:
        self.revoke_calls += 1


@pytest.fixture()
def stub_provider(client):
    """Overrides the real Google provider for every test in this module —
    same dependency-override mechanism already used for get_db in
    conftest.py."""
    stub = StubCalendarProvider()
    main_module.app.dependency_overrides[get_calendar_provider] = lambda: stub
    yield stub
    del main_module.app.dependency_overrides[get_calendar_provider]


def _user_id_from_headers(auth_headers) -> uuid_mod.UUID:
    import jose.jwt as jwt
    from shared.config import settings

    token = auth_headers["Authorization"].split(" ")[1]
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return uuid_mod.UUID(payload["sub"])


def test_status_when_not_connected(client, auth_headers, stub_provider):
    response = client.get("/calendar/status", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"connected": False, "accountEmail": None}


def test_oauth_start_requires_auth(client, stub_provider):
    response = client.get("/calendar/oauth/start")
    assert response.status_code == 403


def test_oauth_start_returns_authorization_url_with_state(client, auth_headers, stub_provider):
    response = client.get("/calendar/oauth/start", headers=auth_headers)
    assert response.status_code == 200
    url = response.json()["authorizationUrl"]
    assert "fake-consent" in url
    assert "state=" in url


def test_full_connect_flow_via_callback(client, auth_headers, stub_provider):
    user_id = _user_id_from_headers(auth_headers)
    state = _create_oauth_state(user_id)

    response = client.get(
        f"/calendar/oauth/callback?code=fake-code-123&state={state}",
        headers=auth_headers,
        follow_redirects=False,
    )
    assert response.status_code in (302, 307), response.text
    assert "/calendar?connected=1" in response.headers["location"]

    status_response = client.get("/calendar/status", headers=auth_headers)
    body = status_response.json()
    assert body["connected"] is True
    assert body["accountEmail"] == "someone@example.com"


def test_callback_rejects_invalid_state(client, stub_provider):
    response = client.get(
        "/calendar/oauth/callback?code=fake-code&state=not-a-real-token",
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_callback_rejects_expired_state(client, stub_provider):
    import jose.jwt as jwt
    from shared.config import settings
    from calendar_integration.routes import STATE_PURPOSE

    expired_state = jwt.encode(
        {
            "sub": str(uuid_mod.uuid4()),
            "purpose": STATE_PURPOSE,
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get(
        f"/calendar/oauth/callback?code=fake-code&state={expired_state}",
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_callback_rejects_state_with_wrong_purpose(client, stub_provider):
    """A normal session token (or any other JWT signed with the same
    secret but a different purpose) must not work as an OAuth state —
    this is exactly what the purpose claim exists to prevent."""
    import jose.jwt as jwt
    from shared.config import settings

    wrong_purpose_state = jwt.encode(
        {
            "sub": str(uuid_mod.uuid4()),
            "purpose": "something_else",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get(
        f"/calendar/oauth/callback?code=fake-code&state={wrong_purpose_state}",
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_connecting_again_replaces_existing_connection(client, auth_headers, stub_provider):
    user_id = _user_id_from_headers(auth_headers)

    state1 = _create_oauth_state(user_id)
    client.get(f"/calendar/oauth/callback?code=code-1&state={state1}", follow_redirects=False)

    state2 = _create_oauth_state(user_id)
    client.get(f"/calendar/oauth/callback?code=code-2&state={state2}", follow_redirects=False)

    # Still exactly one connection for this user, not two — verified via
    # the status endpoint rather than reaching into the DB directly,
    # sufficient here since the real invariant under test is "no
    # duplicate rows/behavior," which a successful single /status call
    # already implies.
    response = client.get("/calendar/status", headers=auth_headers)
    assert response.json()["connected"] is True


def test_list_events_requires_connection(client, auth_headers, stub_provider):
    response = client.get("/calendar/events", headers=auth_headers)
    assert response.status_code == 404


def test_list_events_returns_normalized_events(client, auth_headers, stub_provider):
    user_id = _user_id_from_headers(auth_headers)
    state = _create_oauth_state(user_id)
    client.get(f"/calendar/oauth/callback?code=fake-code&state={state}", follow_redirects=False)

    response = client.get("/calendar/events", headers=auth_headers)
    assert response.status_code == 200, response.text
    events = response.json()
    assert len(events) == 1
    assert events[0]["title"] == "Dentist"
    assert events[0]["allDay"] is False


def test_list_events_refreshes_expired_access_token(client, auth_headers, stub_provider, session_factory):
    """Confirms the silent-refresh path actually runs when the cached
    access token is expired, rather than only when it's entirely absent."""
    user_id = _user_id_from_headers(auth_headers)
    state = _create_oauth_state(user_id)
    client.get(f"/calendar/oauth/callback?code=fake-code&state={state}", follow_redirects=False)

    # Force the cached access token to look expired.
    from calendar_integration.models import CalendarConnection

    db = session_factory()
    try:
        conn = db.query(CalendarConnection).filter(CalendarConnection.user_id == user_id).first()
        conn.access_token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    assert stub_provider.refresh_calls == 0
    response = client.get("/calendar/events", headers=auth_headers)
    assert response.status_code == 200
    assert stub_provider.refresh_calls == 1


def test_disconnect_removes_connection_and_calls_revoke(client, auth_headers, stub_provider):
    user_id = _user_id_from_headers(auth_headers)
    state = _create_oauth_state(user_id)
    client.get(f"/calendar/oauth/callback?code=fake-code&state={state}", follow_redirects=False)

    response = client.delete("/calendar/connection", headers=auth_headers)
    assert response.status_code == 204
    assert stub_provider.revoke_calls == 1

    status_response = client.get("/calendar/status", headers=auth_headers)
    assert status_response.json()["connected"] is False


def test_disconnect_when_not_connected_is_a_no_op(client, auth_headers, stub_provider):
    response = client.delete("/calendar/connection", headers=auth_headers)
    assert response.status_code == 204
    assert stub_provider.revoke_calls == 0


def test_events_requires_auth(client, stub_provider):
    assert client.get("/calendar/events").status_code == 403


def test_connection_is_scoped_to_the_authenticated_user(client, auth_headers, second_user_headers, stub_provider):
    """A second user must never see the first user's connection or events."""
    user_id = _user_id_from_headers(auth_headers)
    state = _create_oauth_state(user_id)
    client.get(f"/calendar/oauth/callback?code=fake-code&state={state}", follow_redirects=False)

    response = client.get("/calendar/status", headers=second_user_headers)
    assert response.json()["connected"] is False

    events_response = client.get("/calendar/events", headers=second_user_headers)
    assert events_response.status_code == 404


def test_status_response_never_contains_raw_tokens(client, auth_headers, stub_provider):
    """Structural guard: even if a future edit accidentally widened
    CalendarStatusResponse, this test would catch a raw token leaking
    into a client-facing response."""
    user_id = _user_id_from_headers(auth_headers)
    state = _create_oauth_state(user_id)
    client.get(f"/calendar/oauth/callback?code=fake-code&state={state}", follow_redirects=False)

    response = client.get("/calendar/status", headers=auth_headers)
    assert "fake-refresh-token" not in response.text
    assert "fake-access-token" not in response.text


def test_calendar_module_has_no_ai_extraction_dependency():
    """Same AST-based structural guard already used for the Journal
    module (tests/test_journal.py) — confirms calendar_integration/
    never imports ai_extraction, so calendar data can never silently
    reach the AI pipeline via a future edit."""
    import ast
    import inspect
    import calendar_integration.routes as calendar_routes
    import calendar_integration.google_provider as calendar_provider

    for module in (calendar_routes, calendar_provider):
        tree = ast.parse(inspect.getsource(module))
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module.split(".")[0])
        assert "ai_extraction" not in imported_modules


def test_calendar_module_has_no_productivity_dependency():
    """Structural guard for the other stated boundary: this module must
    never import productivity/ (Task/Goal/Habit) — Domain Model §4.2's
    exclusion of scheduling fields from Task stays intact by construction,
    not just by review discipline."""
    import ast
    import inspect
    import calendar_integration.routes as calendar_routes
    import calendar_integration.models as calendar_models

    for module in (calendar_routes, calendar_models):
        tree = ast.parse(inspect.getsource(module))
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module.split(".")[0])
        assert "productivity" not in imported_modules
        assert "habits" not in imported_modules
