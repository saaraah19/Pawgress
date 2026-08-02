"""
productivity/schemas.py — request/response shapes for capture/task endpoints.

Distinct from the SQLAlchemy models in models.py: these define what the API
actually exposes to the client, which is deliberately narrower than the full
database row (e.g., FieldCorrectionRecord has no schema here at all — BR-4,
Domain Model Invariant 7: it must never be exposed through any client-facing path).
"""

import uuid
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel


class CaptureRequest(BaseModel):
    rawText: str


class TaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    category: str
    priority: Literal["Low", "Medium", "High"]
    estimateMinutes: Optional[int]
    status: Literal["NotStarted", "Done"]
    origin: Literal["AIGenerated", "ManuallyCreated"]
    createdAt: datetime

    @classmethod
    def from_model(cls, task) -> "TaskResponse":
        """Explicit field-by-field mapping from the SQLAlchemy Task model
        (snake_case columns) to the API's camelCase contract. Deliberately
        explicit rather than relying on Pydantic's automatic from_attributes
        matching, which does NOT bridge estimate_minutes -> estimateMinutes
        or created_at -> createdAt on its own — that mismatch would fail
        silently/crash at runtime if left implicit."""
        return cls(
            id=task.id,
            title=task.title,
            category=task.category,
            priority=task.priority.value,
            estimateMinutes=task.estimate_minutes,
            status=task.status.value,
            origin=task.origin.value,
            createdAt=task.created_at,
        )


class CaptureResponse(BaseModel):
    id: uuid.UUID
    rawText: str
    status: Literal["Pending", "Succeeded", "Failed"]
    createdAt: datetime

    @classmethod
    def from_model(cls, capture) -> "CaptureResponse":
        """Same explicit-mapping approach as TaskResponse.from_model, and for
        the same reason — Capture's raw_text/created_at columns don't match
        the API's rawText/createdAt names automatically."""
        return cls(
            id=capture.id,
            rawText=capture.raw_text,
            status=capture.status.value,
            createdAt=capture.created_at,
        )


class CaptureResult(BaseModel):
    """The full response shape for POST /captures — matches the approved API
    contract exactly: capture + tasks in one response, failureReason present
    only when extraction didn't succeed. Per System Architecture §11 step 4:
    no second round trip needed to render the First Capture moment."""
    capture: CaptureResponse
    tasks: list[TaskResponse]
    failureReason: Optional[Literal["schema_invalid", "provider_error"]] = None


class TaskUpdateRequest(BaseModel):
    """Every field optional — a correction can touch just one field (FR-4.1),
    with no confirmation step implied by the shape of this contract (FR-4.2).

    `status` added per FR-3.3, which already names status alongside title/
    category/priority/estimate as an approved MVP-editable field — this was
    a contract omission against an already-settled requirement, not a new
    product decision. Marking a task Done is the ordinary Completing-and-
    Reflecting interaction (UX Philosophy §5.3), not an AI-field correction,
    which is why it's excluded from correction-tracking in routes.py below."""
    title: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[Literal["Low", "Medium", "High"]] = None
    estimateMinutes: Optional[int] = None
    status: Optional[Literal["NotStarted", "Done"]] = None