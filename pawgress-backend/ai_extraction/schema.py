"""
ai_extraction/schema.py

Defines the exact shape the AI is allowed to return, and validates raw model
output against it. Whole-response validation, per the approved Slice 1 decision:
if any part of the response is malformed, the entire response is rejected — no
partial salvage of individual tasks (System Architecture §20: "a partially-parsed,
guessed structure is a worse outcome than a clean failure").

This mirrors the spike's schema_validator.py logic — same contract, now the
production version that ExtractionService actually calls.
"""

import json
from typing import Optional, Literal

from pydantic import BaseModel, ValidationError, field_validator


class ExtractedTask(BaseModel):
    title: str
    category: str
    priority: Literal["Low", "Medium", "High"]
    estimateMinutes: Optional[int] = None

    @field_validator("title", "category")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v

    @field_validator("estimateMinutes")
    @classmethod
    def positive_if_present(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("estimateMinutes must be positive if provided")
        return v

    model_config = {"extra": "forbid"}  # reject unexpected fields — part of
    # whole-response validation, not just missing/wrong-type fields


class ExtractionResponse(BaseModel):
    tasks: list[ExtractedTask]

    model_config = {"extra": "forbid"}


class SchemaValidationError(Exception):
    def __init__(self, reason: str, raw: str):
        self.reason = reason
        self.raw = raw
        super().__init__(reason)


def validate_extraction_response(raw_text: str) -> ExtractionResponse:
    """Raises SchemaValidationError on ANY deviation from the contract —
    not valid JSON, wrong shape, extra fields, wrong types. No partial trust."""
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise SchemaValidationError(f"not valid JSON: {e}", raw_text)

    try:
        return ExtractionResponse.model_validate(parsed)
    except ValidationError as e:
        raise SchemaValidationError(str(e), raw_text)
