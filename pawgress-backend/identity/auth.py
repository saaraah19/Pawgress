"""
identity/auth.py

Password hashing and session token creation/verification. Per Handover §3:
"the least memorable part of the product, on purpose" — kept deliberately
simple, standard library choices, no bespoke crypto.

Uses the `bcrypt` library directly rather than through `passlib`. passlib
1.7.4 (the latest release) has a known, long-standing incompatibility with
bcrypt >=4.x — it tries to read a `bcrypt.__about__.__version__` attribute
that newer bcrypt releases removed, which crashes at hash time (not install
time), so it passes `pip install` cleanly and only breaks on first real use.
passlib is effectively unmaintained (last release 2020), so this avoids the
fragile version-detection layer entirely rather than fighting pin versions.
"""

from datetime import datetime, timedelta, timezone
import uuid

import bcrypt
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from shared.config import settings
from shared.database import get_db
from identity.models import User

bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    # bcrypt has a 72-byte input limit — truncate defensively rather than
    # letting it silently ignore anything past that (bcrypt's own behavior),
    # which matters if we ever raise the minimum password length later.
    password_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    password_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency — every protected endpoint takes this as a parameter.
    This is the single, consistently-applied authorization rule from System
    Architecture §9: every request is scoped to exactly the authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user