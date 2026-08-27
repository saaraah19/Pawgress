"""
calendar_integration/google_provider.py

Calendar Provider abstraction — same shape-of-reasoning as
ai_extraction/provider.py: no other module ever calls Google's API
directly. Deliberately NOT a generalized multi-provider registry — Google
Calendar is the only provider this slice supports (explicit scope
decision, 2026-08-19). The interface exists so a second provider is a new
class later, not a rewrite, without building speculative abstraction now.

Uses plain HTTP via httpx rather than Google's official
google-api-python-client / google-auth-oauthlib stack. The OAuth token
exchange and events.list call are both simple REST endpoints; pulling in
the full official SDK would add a meaningfully heavier dependency chain
for what two direct HTTP calls already cover cleanly — matches this
codebase's existing pattern of a thin REST wrapper (ai_extraction/provider.py
does the same against Groq's OpenAI-compatible endpoint rather than a
heavier client). This is a technical implementation choice, not a product
decision.

IMPORTANT, stated plainly rather than implied: the real, live OAuth
consent-screen handshake against Google's actual servers CANNOT be
exercised from this development sandbox (no network path to
accounts.google.com here). Everything in this file is verified by unit
tests against a stub implementation of the CalendarProvider interface —
that proves this code constructs the right requests and handles responses
correctly, but it is NOT equivalent to a live end-to-end test against
Google's real servers. See docs/PROGRESS.md for the manual verification
steps required locally, with real credentials, before this is considered
fully proven.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx

from shared.config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

# Events-only, read-only — the minimal scope for what this slice actually
# needs (list events on the primary calendar). Deliberately narrower than
# the broader `calendar.readonly` scope, which also grants calendar
# list/settings visibility this feature never uses.
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly"

DEFAULT_DAYS_AHEAD = 14


@dataclass
class GoogleTokens:
    access_token: str
    refresh_token: Optional[str]
    expires_at: datetime


@dataclass
class NormalizedEvent:
    id: str
    title: str
    start: datetime
    end: datetime
    all_day: bool
    location: Optional[str]


class CalendarProvider:
    """Interface every concrete provider implements — one method per
    actual need, no speculative surface area, same reasoning as
    ai_extraction/provider.py's ModelProvider."""

    def build_authorization_url(self, state: str) -> str:
        raise NotImplementedError

    def exchange_code_for_tokens(self, code: str) -> GoogleTokens:
        raise NotImplementedError

    def get_account_email(self, access_token: str) -> Optional[str]:
        raise NotImplementedError

    def refresh_access_token(self, refresh_token: str) -> GoogleTokens:
        raise NotImplementedError

    def list_events(self, access_token: str, days_ahead: int = DEFAULT_DAYS_AHEAD) -> list[NormalizedEvent]:
        raise NotImplementedError

    def revoke(self, token: str) -> None:
        raise NotImplementedError


class CalendarNotConfiguredError(Exception):
    """Raised when Google OAuth credentials aren't set. Calendar is an
    opt-in feature — unlike DATABASE_URL/GROQ_API_KEY/JWT_SECRET, missing
    Google credentials should not crash the whole app at startup (someone
    who never touches Calendar shouldn't be blocked from running Pawgress
    at all), but a route that actually needs them should fail clearly,
    not silently build a broken authorization URL."""


class GoogleCalendarProvider(CalendarProvider):
    def _require_configured(self) -> None:
        if not settings.google_client_id or not settings.google_client_secret:
            raise CalendarNotConfiguredError(
                "Google Calendar isn't configured on this server yet "
                "(GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET missing)."
            )

    def build_authorization_url(self, state: str) -> str:
        self._require_configured()
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": CALENDAR_SCOPE,
            "access_type": "offline",  # required to receive a refresh_token
            "prompt": "consent",  # forces the consent screen (and a fresh
            # refresh_token) even on a repeat connect — matches "connecting
            # again replaces the existing connection" (approved default).
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def exchange_code_for_tokens(self, code: str) -> GoogleTokens:
        self._require_configured()
        response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15.0,
        )
        response.raise_for_status()
        body = response.json()
        return GoogleTokens(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=body.get("expires_in", 3600)),
        )

    def get_account_email(self, access_token: str) -> Optional[str]:
        response = httpx.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15.0,
        )
        if response.status_code != 200:
            return None
        return response.json().get("email")

    def refresh_access_token(self, refresh_token: str) -> GoogleTokens:
        self._require_configured()
        response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
            },
            timeout=15.0,
        )
        response.raise_for_status()
        body = response.json()
        return GoogleTokens(
            access_token=body["access_token"],
            # Google does not reissue a refresh_token on a plain refresh
            # call — the original one remains valid and must be kept.
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=body.get("expires_in", 3600)),
        )

    def list_events(self, access_token: str, days_ahead: int = DEFAULT_DAYS_AHEAD) -> list[NormalizedEvent]:
        now = datetime.now(timezone.utc)
        params = {
            "timeMin": now.isoformat(),
            "timeMax": (now + timedelta(days=days_ahead)).isoformat(),
            # Expands recurring events into real individual occurrences —
            # required for a genuine chronological list, not a style choice.
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 250,
        }
        response = httpx.get(
            GOOGLE_CALENDAR_EVENTS_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=15.0,
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        return [_normalize_event(item) for item in items if item.get("status") != "cancelled"]

    def revoke(self, token: str) -> None:
        httpx.post(GOOGLE_REVOKE_URL, params={"token": token}, timeout=15.0)


def _normalize_event(item: dict) -> NormalizedEvent:
    start_data = item.get("start", {})
    end_data = item.get("end", {})
    # Google represents all-day events with a "date" field (YYYY-MM-DD)
    # instead of "dateTime" (full ISO timestamp with timezone offset).
    all_day = "date" in start_data

    if all_day:
        start = datetime.fromisoformat(start_data["date"]).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(end_data["date"]).replace(tzinfo=timezone.utc)
    else:
        start = datetime.fromisoformat(start_data["dateTime"])
        end = datetime.fromisoformat(end_data["dateTime"])

    return NormalizedEvent(
        id=item["id"],
        title=item.get("summary") or "(No title)",
        start=start,
        end=end,
        all_day=all_day,
        location=item.get("location"),
    )


def get_calendar_provider() -> CalendarProvider:
    """Single point of construction — mirrors
    ai_extraction/provider.py's get_model_provider(). Used as a FastAPI
    dependency (Depends(get_calendar_provider)) rather than called inline
    inside each route body, unlike get_model_provider()'s usage in
    productivity/routes.py — a deliberate, small divergence: it lets tests
    override the provider via app.dependency_overrides and exercise the
    real HTTP routes end-to-end (state verification, redirects, error
    handling), rather than only testing an inner service function in
    isolation, which matters more here given how much of this feature's
    real complexity lives in the routing/redirect layer itself."""
    return GoogleCalendarProvider()
