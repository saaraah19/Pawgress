"""
shared/config.py

Central place for configuration values. Everything here comes from environment
variables — nothing sensitive (API keys, DB credentials, JWT secret) is ever
hardcoded in source, per System Architecture §17's secrets-management rule.

Usage: `from shared.config import settings` then `settings.database_url`, etc.
"""

import os
from functools import lru_cache
from dotenv import load_dotenv

# Loads variables from a .env file in the current directory into the process's
# environment, so os.environ.get(...) below actually sees them. Without this
# call, a correctly-filled .env file would be silently ignored — this must run
# BEFORE any os.environ.get() calls happen, which is why it's at module level,
# at the top of the file.
load_dotenv()


class Settings:
    # --- Database ---
    # Format: postgresql://user:password@host:port/dbname
    # Free-tier Postgres (e.g. Neon) provides this connection string directly.
    _raw_database_url: str = os.environ.get("DATABASE_URL", "")

    @property
    def database_url(self) -> str:
        """
        Neon (and most providers) give you a plain `postgresql://...` or
        `postgres://...` connection string. SQLAlchemy defaults that scheme
        to the psycopg2 driver, but this project uses psycopg (v3) instead,
        because psycopg2-binary has no prebuilt package for newer Python
        versions (e.g. 3.13/3.14) and fails to install without local
        PostgreSQL build tools. This normalizes whatever URL you paste into
        .env into the `postgresql+psycopg://` form psycopg v3 needs — paste
        Neon's URL exactly as given, no manual editing required.
        """
        url = self._raw_database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and "+psycopg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    # --- Auth ---
    # Used to sign session tokens. No insecure fallback: an app whose session
    # tokens can be forged by anyone who's read this file's git history is a
    # real security hole, not a convenience worth keeping — so this is
    # required at startup exactly like DATABASE_URL and GROQ_API_KEY below,
    # rather than silently defaulting to a value that's public in source
    # control. Generate one locally with:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    jwt_secret: str = os.environ.get("JWT_SECRET", "")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days — FR-1.2's
    # "stay authenticated across sessions" requirement, without building a
    # separate refresh-token flow yet (that's a reasonable Slice 1 simplification,
    # not a documented requirement — flagging it as my call, not a Blueprint rule).

    # --- AI/Extraction (Groq) ---
    groq_api_key: str = os.environ.get("GROQ_API_KEY", "")
    groq_base_url: str = "https://api.groq.com/openai/v1"
    # Locked per the executed spike — see cost_model.md's decision banner and
    # ai_extraction/prompt.py for the exact system prompt this was validated against.
    extraction_model: str = "openai/gpt-oss-120b"

    # --- CORS ---
    # Comma-separated list of allowed origins. Least-privilege (System
    # Architecture §17) still applies — this is NOT a wildcard — but a
    # single hardcoded origin turned out to be real local-dev friction:
    # "localhost:5173" and "127.0.0.1:5173" are the same Vite dev server to
    # a person, but two different origins to a browser's CORS check, and
    # which one a given machine resolves by default varies (this is the
    # same localhost/127.0.0.1 inconsistency already flagged for the
    # Windows dev environment elsewhere in this project). Defaulting to
    # both covers local dev without weakening anything for a real
    # deployment, where FRONTEND_ORIGIN should still be set explicitly to
    # the one real frontend URL.
    frontend_origin: str = os.environ.get(
        "FRONTEND_ORIGIN", "http://127.0.0.1:5173,http://localhost:5173"
    )

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    # --- Calendar (Google, read-only, v1) ---
    # NOT included in validate()'s required-startup check below — Calendar
    # is opt-in (Blueprint's general "AI-first does not mean AI-only"
    # spirit extended here: a feature nobody has connected yet shouldn't
    # block the whole app from starting the way a missing DATABASE_URL
    # would). A route that actually needs these fails clearly instead
    # (see calendar_integration/google_provider.py's CalendarNotConfiguredError).
    google_client_id: str = os.environ.get("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    google_oauth_redirect_uri: str = os.environ.get(
        "GOOGLE_OAUTH_REDIRECT_URI", "http://127.0.0.1:8000/calendar/oauth/callback"
    )

    def validate(self) -> None:
        """Fail loudly at startup if required secrets are missing, rather than
        failing confusingly on the first real request."""
        missing = []
        if not self.database_url:
            missing.append("DATABASE_URL")
        if not self.groq_api_key:
            missing.append("GROQ_API_KEY")
        if not self.jwt_secret:
            missing.append("JWT_SECRET")
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Set these before starting the app."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
