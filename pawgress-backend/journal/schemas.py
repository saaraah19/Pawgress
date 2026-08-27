"""
journal/schemas.py — request/response shapes for the Journal module.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class JournalEntryCreateRequest(BaseModel):
    # Same generous ceiling and same reasoning as CaptureRequest.rawText
    # (productivity/schemas.py) — a plain guard against an unbounded string,
    # not a product-imposed length limit on reflection.
    text: str = Field(..., min_length=1, max_length=5000)


class JournalEntryUpdateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


class JournalEntryResponse(BaseModel):
    id: uuid.UUID
    text: str
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, entry) -> "JournalEntryResponse":
        return cls(
            id=entry.id,
            text=entry.text,
            createdAt=entry.created_at,
            updatedAt=entry.updated_at,
        )
