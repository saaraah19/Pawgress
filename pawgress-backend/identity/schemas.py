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
