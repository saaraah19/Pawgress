"""
calendar_integration/routes.py

Read-only Google Calendar integration (explicit scope decision,
2026-08-19): Google -> Pawgress only. No writes to Google, ever. No
import of ai_extraction anywhere in this module — verified structurally
by tests/test_calendar.py's AST-based guard, same pattern already used
for journal/routes.py. No relationship to Task/Goal/Habit.

OAuth `state` handling, worth explaining once here since it's the least
obvious part of this module: /calendar/oauth/callback is hit directly by
the browser via Google's redirect — it never carries this app's own
Bearer token, so it can't use get_current_user the normal way. The naive
fix (a server-side dict mapping state -> user_id, populated in
/oauth/start) was considered and rejected: an in-memory map would not
survive across worker processes in a real multi-replica deployment,
directly violating System Architecture §22's "stateless replicas, no
session state in server memory" constraint. Instead, `state` IS a
short-lived, signed JWT (same secret/mechanism as session tokens,
identity/auth.py) embedding the user id and a distinct "purpose" claim.
No server-side storage at all; verified purely by signature + expiry on
the callback, and the purpose claim stops a normal session token (or vice
versa) from being usable as an OAuth state token.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.config import settings
from identity.auth import get_current_user
from identity.models import User
from calendar_integration.models import CalendarConnection
from calendar_integration.schemas import (
    CalendarStatusResponse,
    CalendarOAuthStartResponse,
    CalendarEventResponse,
)
from calendar_integration.google_provider import (
    get_calendar_provider,
    CalendarProvider,
    CalendarNotConfiguredError,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])

STATE_PURPOSE = "calendar_oauth"
STATE_EXPIRE_MINUTES = 10  # generous window to actually complete Google's consent screen


def _create_oauth_state(user_id: uuid.UUID) -> str:
    payload = {
        "sub": str(user_id),
        "purpose": STATE_PURPOSE,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=STATE_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _verify_oauth_state(state: str) -> uuid.UUID:
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This connection request has expired or is invalid. Try connecting again.",
        )
    if payload.get("purpose") != STATE_PURPOSE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid connection request.")
    return uuid.UUID(payload["sub"])


def _get_valid_access_token(db: Session, connection: CalendarConnection, provider: CalendarProvider) -> str:
    """Returns a usable access token, silently refreshing if the cached
    one is missing or expired. Never exposes this mechanic to the caller.

    Normalizes a naive `access_token_expires_at` to UTC before comparing:
    confirmed directly that SQLite (the test harness's dialect,
    tests/conftest.py) silently strips timezone awareness from a
    DateTime(timezone=True) column on round-trip through SQLAlchemy,
    while real Postgres preserves it correctly — comparing a naive and an
    aware datetime raises TypeError, which the route's broad
    exception handler would otherwise mask as a generic "couldn't reach
    Google" error, hiding a real bug behind a plausible-looking one. This
    fallback makes the comparison correct on both dialects rather than
    only ever being exercised against real Postgres."""
    now = datetime.now(timezone.utc)
    expires_at = connection.access_token_expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if connection.access_token and expires_at and expires_at > now:
        return connection.access_token

    tokens = provider.refresh_access_token(connection.refresh_token)
    connection.access_token = tokens.access_token
    connection.access_token_expires_at = tokens.expires_at
    db.commit()
    return tokens.access_token


@router.get("/status", response_model=CalendarStatusResponse)
def get_calendar_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    connection = db.query(CalendarConnection).filter(CalendarConnection.user_id == current_user.id).first()
    if not connection:
        return CalendarStatusResponse(connected=False)
    return CalendarStatusResponse(connected=True, accountEmail=connection.google_account_email)


@router.get("/oauth/start", response_model=CalendarOAuthStartResponse)
def start_oauth(
    current_user: User = Depends(get_current_user),
    provider: CalendarProvider = Depends(get_calendar_provider),
):
    state = _create_oauth_state(current_user.id)
    try:
        url = provider.build_authorization_url(state)
    except CalendarNotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return CalendarOAuthStartResponse(authorizationUrl=url)


@router.get("/oauth/callback")
def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
    provider: CalendarProvider = Depends(get_calendar_provider),
):
    """Hit directly by Google's redirect — no Bearer token, no
    get_current_user. User identity comes entirely from the signed
    `state` value created in start_oauth above."""
    user_id = _verify_oauth_state(state)

    tokens = provider.exchange_code_for_tokens(code)
    account_email = provider.get_account_email(tokens.access_token)

    existing = db.query(CalendarConnection).filter(CalendarConnection.user_id == user_id).first()
    if existing:
        # Connecting again replaces the existing connection (approved
        # default — no multi-account support in v1). Google only returns
        # a refresh_token on the FIRST authorization for a given consent;
        # a subsequent one may omit it, so keep the old one if so.
        existing.refresh_token = tokens.refresh_token or existing.refresh_token
        existing.access_token = tokens.access_token
        existing.access_token_expires_at = tokens.expires_at
        existing.google_account_email = account_email
    else:
        db.add(
            CalendarConnection(
                id=uuid.uuid4(),
                user_id=user_id,
                provider="google",
                refresh_token=tokens.refresh_token,
                access_token=tokens.access_token,
                access_token_expires_at=tokens.expires_at,
                google_account_email=account_email,
            )
        )
    db.commit()

    frontend_url = settings.frontend_origins[0] if settings.frontend_origins else "/"
    return RedirectResponse(url=f"{frontend_url}/calendar?connected=1")


@router.get("/events", response_model=list[CalendarEventResponse])
def list_calendar_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider: CalendarProvider = Depends(get_calendar_provider),
):
    connection = db.query(CalendarConnection).filter(CalendarConnection.user_id == current_user.id).first()
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No calendar connected.")

    try:
        access_token = _get_valid_access_token(db, connection, provider)
        events = provider.list_events(access_token)
    except HTTPException:
        raise
    except Exception:
        # A refresh/API failure (e.g. the user revoked access from their
        # Google account settings) should read as "reconnect," not a raw
        # 500 — the connection row is deliberately left in place so
        # /status still shows "connected" until the user explicitly
        # disconnects or successfully reconnects, which is the honest,
        # non-alarming failure mode here.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't reach Google Calendar just now. Try reconnecting if this keeps happening.",
        )

    return [
        CalendarEventResponse(id=e.id, title=e.title, start=e.start, end=e.end, allDay=e.all_day, location=e.location)
        for e in events
    ]


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_calendar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider: CalendarProvider = Depends(get_calendar_provider),
):
    connection = db.query(CalendarConnection).filter(CalendarConnection.user_id == current_user.id).first()
    if not connection:
        return  # disconnecting when nothing is connected is a graceful no-op

    try:
        provider.revoke(connection.refresh_token)
    except Exception:
        # Best-effort revoke: even if Google's revoke call fails, our own
        # stored copy is still removed below, since that's the part
        # actually within this app's control. A user can also revoke
        # access directly from their Google account's security settings
        # if this ever matters.
        pass

    db.delete(connection)
    db.commit()
