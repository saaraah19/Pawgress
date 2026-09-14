"""
identity/password_reset.py

Pre-deployment security pass (2026-09-13). Deliberately implemented as a
short-lived, purpose-scoped JWT reusing the existing jwt_secret — NOT a
new database table. Two reasons:
  1. No schema/DB migration needed for a feature that's otherwise pure
     application logic — the standing collaboration rule is to always
     stop and ask before a schema change, and this sidesteps needing to.
  2. A reset token doesn't need to be revocable/listable the way a
     refresh token might (System Architecture §9 describes a refresh-
     token pattern that was never actually implemented, see
     identity/auth.py) — it just needs to prove "whoever holds this link
     recently proved control of this email address," which a signed,
     time-limited, single-purpose token does perfectly well on its own.

**The real gap this module does NOT close:** actually sending an email.
`send_password_reset_email` below is a genuine, working seam — it logs
the reset link so it's visible in local dev — but there is no real email
provider wired up, because that requires choosing a provider (SendGrid,
Postmark, AWS SES, plain SMTP through an existing account, ...) and
supplying real credentials, both of which are Sarah's call, not mine.
Wiring in a real provider once she's chosen one is a small, contained
change to this one function.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError

from shared.config import settings

logger = logging.getLogger("pawgress.password_reset")

RESET_TOKEN_PURPOSE = "password_reset"
RESET_TOKEN_EXPIRE_MINUTES = 30  # short-lived on purpose — this is a security-sensitive token, unlike the 7-day access token


def create_password_reset_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire, "purpose": RESET_TOKEN_PURPOSE}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_password_reset_token(token: str) -> Optional[uuid.UUID]:
    """Returns the user_id if the token is valid, unexpired, AND was
    actually issued for password-reset (the `purpose` claim) — without
    that last check, a valid but expired-for-different-reasons access
    token, or any other JWT signed with the same secret, could otherwise
    be replayed here as if it were a reset token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None

    if payload.get("purpose") != RESET_TOKEN_PURPOSE:
        return None

    user_id_str = payload.get("sub")
    if user_id_str is None:
        return None

    try:
        return uuid.UUID(user_id_str)
    except ValueError:
        return None


def send_password_reset_email(email: str, token: str) -> None:
    """SEAM FOR REAL EMAIL DELIVERY — see this module's docstring. For now,
    this only logs the reset link (visible in local dev / server logs),
    which is enough to test the flow end-to-end but is NOT a real delivery
    mechanism. Deliberately does not log the token as a bare value without
    context, to make it slightly less likely to be copy-pasted somewhere
    it shouldn't be by accident."""
    reset_link = f"{settings.frontend_origins[0]}/reset-password?token={token}"
    logger.info(
        "Password reset requested for %s. (No real email provider configured yet — "
        "this link would normally be emailed, not logged: %s)",
        email,
        reset_link,
    )
