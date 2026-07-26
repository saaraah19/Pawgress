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
    # Used to sign session tokens. Generate a real random secret for production —
    # never use the fallback below outside local development.
    jwt_secret: str = os.environ.get("JWT_SECRET", "dev-only-insecure-secret-change-me")
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

    def validate(self) -> None:
        """Fail loudly at startup if required secrets are missing, rather than
        failing confusingly on the first real request."""
        missing = []
        if not self.database_url:
            missing.append("DATABASE_URL")
        if not self.groq_api_key:
            missing.append("GROQ_API_KEY")
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Set these before starting the app."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
