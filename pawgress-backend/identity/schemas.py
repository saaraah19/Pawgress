"""
identity/schemas.py — request/response shapes for auth endpoints.
"""

import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def minimum_length(cls, v: str) -> str:
        # Minimum security requirement per AC-1.1.1 — kept simple for Slice 1,
        # not a full password-strength policy.
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user_id: uuid.UUID
    access_token: str


class ProfileResponse(BaseModel):
    """FR-1.3 — the neutral default ('Friend') is applied here, at the API
    layer, never stored on the User row. A NULL display_name in the
    database *is* "no display name set yet" (identity/models.py); this is
    where that NULL becomes something presentable, so the frontend never
    has to know the difference between "no name" and "named Friend."""
    user_id: uuid.UUID
    display_name: str
    email: str


class PasswordResetRequestRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def minimum_length(cls, v: str) -> str:
        # Same floor as RegisterRequest's — a password reset shouldn't be
        # held to a lower bar than account creation was.
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v


class ProfileUpdateRequest(BaseModel):
    """Account-management floor, 2026-09-13 — the one previously-missing
    piece of FR-1.3's 'minimal profile' that had no way to actually be
    edited by the user. Only display_name for now (email/password changes
    are a real security-surface decision, deliberately not bundled in
    here without a separate look at re-verification/re-auth flows)."""
    display_name: Optional[str] = None

    @field_validator("display_name")
    @classmethod
    def blank_becomes_none(cls, v: Optional[str]) -> Optional[str]:
        # An empty/whitespace-only name should behave like "no name set"
        # (falls back to the neutral default), not persist as a literal
        # empty string that would then render as a blank profile field.
        if v is not None and not v.strip():
            return None
        return v.strip() if v is not None else None