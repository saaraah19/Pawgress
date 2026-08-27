"""
productivity/schemas.py — request/response shapes for capture/task/goal endpoints.

Distinct from the SQLAlchemy models in models.py: these define what the API
actually exposes to the client, which is deliberately narrower than the full
database row (e.g., FieldCorrectionRecord has no schema here at all — BR-4,
Domain Model Invariant 7: it must never be exposed through any client-facing path).
"""

import uuid
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class CaptureRequest(BaseModel):
    # max_length=5000: a plain, generous ceiling on raw capture text — not a
    # product constraint (nothing in FR-2.1 implies a limit beyond "arbitrary
    # length within a reasonable technical maximum"), just a guard against an
    # unbounded string being forwarded straight into an LLM call on every
    # request (cost and abuse surface, System Architecture §17).
    rawText: str = Field(..., max_length=5000)


class TaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    category: Optional[str]
    priority: Literal["Low", "Medium", "High"]
    estimateMinutes: Optional[int]
    status: Literal["NotStarted", "Done"]
    origin: Literal["AIGenerated", "ManuallyCreated"]
    goalId: Optional[uuid.UUID]
    createdAt: datetime

    @classmethod
    def from_model(cls, task) -> "TaskResponse":
        """Explicit field-by-field mapping from the SQLAlchemy Task model
        (snake_case columns) to the API's camelCase contract. Deliberately
        explicit rather than relying on Pydantic's automatic from_attributes
        matching, which does NOT bridge estimate_minutes -> estimateMinutes,
        goal_id -> goalId, or created_at -> createdAt on its own — that
        mismatch would fail silently/crash at runtime if left implicit."""
        return cls(
            id=task.id,
            title=task.title,
            category=task.category,
            priority=task.priority.value,
            estimateMinutes=task.estimate_minutes,
            status=task.status.value,
            origin=task.origin.value,
            goalId=task.goal_id,
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

    `status` — FR-3.3 already names status alongside title/category/priority/
    estimate as an approved MVP-editable field; this was a contract omission
    against an already-settled requirement, not a new product decision.
    Marking a task Done is the ordinary Completing-and-Reflecting interaction
    (UX Philosophy §5.3), not an AI-field correction, which is why it's
    excluded from correction-tracking in routes.py.

    `goalId` — FR-5.2 optional task-to-goal linking. `None` is a valid,
    meaningful value (unlink), distinct from "field not sent" — routes.py
    uses `exclude_unset=True` so only fields actually present in the request
    body are applied, which lets an explicit `{"goalId": null}` clear the
    link while an absent `goalId` key leaves it untouched.
    """
    title: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[Literal["Low", "Medium", "High"]] = None
    estimateMinutes: Optional[int] = None
    status: Optional[Literal["NotStarted", "Done"]] = None
    goalId: Optional[uuid.UUID] = None


class ManualTaskCreateRequest(BaseModel):
    """FR-3.4 — direct task creation, bypassing the AI Inbox entirely.
    Per AC-3.4.1: only `title` is required; category/priority/estimate are
    either left unset or user-set, never inferred. No `goalId` here —
    goal-linking is discovered contextually after creation (FR-5.3), not part
    of the creation form itself, consistent with UX Philosophy §5.4's
    "structure by invitation, not requirement" — the creation form's job is
    just to get the task into existence with minimum friction."""
    title: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = None
    priority: Optional[Literal["Low", "Medium", "High"]] = None
    estimateMinutes: Optional[int] = None


class GoalCreateRequest(BaseModel):
    """FR-5.1, extended for V2 hierarchy (Blueprint §13). `tier` is optional —
    omitting it creates a flat MVP-style goal with no hierarchy participation
    at all, exactly as before. `parentGoalId` is intentionally NOT accepted
    here: assigning a parent is a separate, deliberate action (PATCH), not
    part of the low-friction creation flow — mirrors FR-3.4's reasoning for
    why manual task creation doesn't accept goalId either (UX Philosophy
    §5.4: structure is discovered, not required up front)."""
    label: str = Field(..., min_length=1, max_length=200)
    tier: Optional[Literal["Annual", "Quarterly", "Project", "Milestone"]] = None


class GoalUpdateRequest(BaseModel):
    """Every field optional, same one-tap-correction shape as
    TaskUpdateRequest — a change can touch just one field, no confirmation
    implied by the contract's shape.

    `parentGoalId`: `None` is a valid, meaningful value (clear the parent),
    distinct from "field not sent" — routes.py uses `exclude_unset=True` so
    an explicit `{"parentGoalId": null}` clears the link while an absent
    key leaves it untouched (identical pattern to TaskUpdateRequest.goalId).
    """
    label: Optional[str] = Field(None, min_length=1, max_length=200)
    tier: Optional[Literal["Annual", "Quarterly", "Project", "Milestone"]] = None
    parentGoalId: Optional[uuid.UUID] = None


class GoalResponse(BaseModel):
    id: uuid.UUID
    label: str
    tier: Optional[Literal["Annual", "Quarterly", "Project", "Milestone"]]
    parentGoalId: Optional[uuid.UUID]
    createdAt: datetime

    @classmethod
    def from_model(cls, goal) -> "GoalResponse":
        return cls(
            id=goal.id,
            label=goal.label,
            tier=goal.tier.value if goal.tier else None,
            parentGoalId=goal.parent_goal_id,
            createdAt=goal.created_at,
        )
