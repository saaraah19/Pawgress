"""
identity/routes.py — FR-1.1 (account creation), FR-1.2 (session persistence).
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from shared.database import get_db
from shared.rate_limit import login_rate_limiter, register_rate_limiter, password_reset_rate_limiter, client_ip
from identity.models import User
from identity.schemas import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    PasswordResetRequestRequest,
    PasswordResetConfirmRequest,
)
from identity.auth import hash_password, verify_password, create_access_token, get_current_user
from identity.account_deletion_service import delete_account
from identity.password_reset import create_password_reset_token, verify_password_reset_token, send_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])

# FR-1.3's neutral placeholder. A plain, warm-enough-not-to-be-cold default
# that never reads as an error state or a forced setup step (BR-1) — this
# is the only place the literal string lives, so changing the default word
# later is a one-line change, not a search-and-replace.
NEUTRAL_DISPLAY_NAME = "Friend"


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    if not register_rate_limiter.allow(client_ip(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again in a little while.",
        )

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        # AC-1.1.2: plain, non-judgmental error message — no blunt technical
        # error, per Brand §6's tone rules extended to system errors.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Try logging in instead.",
        )

    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=None,  # FR-1.3 — no forced value; neutral default is an
        # API/frontend presentation concern, not stored as fake data here.
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    db.refresh(user)

    token = create_access_token(user.id)
    return AuthResponse(user_id=user.id, access_token=token)


@router.get("/me", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """FR-1.3, AC-1.3.1 — a new account with no display name shows the
    neutral default rather than requiring the field to proceed. This is
    the only endpoint that exposes profile data, and it applies the
    default at read time (see NEUTRAL_DISPLAY_NAME above), not at
    account-creation time (identity/routes.py's register() deliberately
    leaves display_name NULL — see identity/models.py's comment)."""
    return ProfileResponse(
        user_id=current_user.id,
        display_name=current_user.display_name or NEUTRAL_DISPLAY_NAME,
        email=current_user.email,
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    if not login_rate_limiter.allow(client_ip(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again in a little while.",
        )

    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    token = create_access_token(user.id)
    return AuthResponse(user_id=user.id, access_token=token)


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(payload: PasswordResetRequestRequest, request: Request, db: Session = Depends(get_db)):
    """Always responds identically whether or not the email is registered
    — same reasoning as login's unified error message: distinguishing the
    two would leak which emails have accounts. Rate-limited by IP (not by
    email) specifically so this can't be used to enumerate registered
    emails via timing/response differences at volume, and so it can't be
    used to spam a single victim's inbox with reset emails from many
    different requesting IPs... well, it can from *many* IPs, but not
    cheaply from one, which is the realistic threat model for a
    pre-launch app."""
    if not password_reset_rate_limiter.allow(client_ip(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again in a little while.",
        )

    user = db.query(User).filter(User.email == payload.email).first()
    if user:
        token = create_password_reset_token(user.id)
        send_password_reset_email(user.email, token)

    return {"detail": "If that email has an account, a reset link has been sent."}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(payload: PasswordResetConfirmRequest, db: Session = Depends(get_db)):
    user_id = verify_password_reset_token(payload.token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That reset link is invalid or has expired. Request a new one.",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # The account was deleted between requesting and confirming the
        # reset — same "don't leak account existence" posture as above.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That reset link is invalid or has expired. Request a new one.",
        )

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    # NOTE: this does not invalidate the user's other existing access
    # tokens (there's no refresh-token/revocation-list infrastructure in
    # this codebase yet — System Architecture §9 describes one but only a
    # single access token is actually implemented, see identity/auth.py).
    # A token issued before the password change remains valid until it
    # naturally expires (up to access_token_expire_minutes). Worth a real
    # look before this matters for a real security incident, not just a
    # forgotten-password convenience flow.


@router.patch("/me", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Account-management floor, 2026-09-13. `exclude_unset` mirrors
    productivity/routes.py's update_task pattern — a request that doesn't
    mention display_name at all leaves it untouched, distinct from a
    request that explicitly sets it to null/empty (which resets to the
    neutral default per FR-1.3)."""
    changes = payload.model_dump(exclude_unset=True)
    if "display_name" in changes:
        current_user.display_name = changes["display_name"]
        db.commit()
        db.refresh(current_user)

    return ProfileResponse(
        user_id=current_user.id,
        display_name=current_user.display_name or NEUTRAL_DISPLAY_NAME,
        email=current_user.email,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_own_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The account-management floor's other half — NFR-3/BR-10's
    architectural requirement ('complete, verifiable per-user deletion')
    finally has a real, callable path, not just an assertion that it would
    theoretically be possible. Self-service, scoped to exactly the
    requesting user's own data (same authorization pattern as every other
    endpoint — current_user.id, never a client-supplied id). Irreversible:
    no confirmation step at this layer (the frontend is where a real
    confirmation belongs, same division of responsibility as every other
    destructive action in this app — see Functional Requirements AC-3.5.1
    on task deletion for the precedent)."""
    delete_account(db, current_user.id)
