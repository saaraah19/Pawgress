"""
identity/schemas.py — request/response shapes for auth endpoints.
"""

import uuid
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
