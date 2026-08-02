"""
productivity/routes.py

FR-2.x (AI Inbox capture), FR-3.x (task list/editing), FR-4.x (one-tap correction).

Authorization rule applied consistently, per System Architecture §9: every
query/mutation here is scoped by the authenticated user's ID as a non-optional
parameter — never an afterthought filter.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from shared.database import get_db
from identity.auth import get_current_user
from identity.models import User
from productivity.models import Task, FieldCorrectionRecord, TaskOrigin
from productivity.schemas import CaptureRequest, CaptureResult, CaptureResponse, TaskResponse, TaskUpdateRequest
from productivity.extraction_service import run_extraction
from ai_extraction.provider import get_model_provider

router = APIRouter(tags=["productivity"])

# FR-4/BR-4 govern corrections on AI-ASSIGNED fields specifically — status
# is excluded on purpose. Marking a task Done is the ordinary Completing-and-
# Reflecting interaction (UX Philosophy §5.3), not "the AI got this wrong,"
# so it must never write a FieldCorrectionRecord or count toward the
# correction-rate metric (Blueprint §17).
CORRECTION_TRACKED_FIELDS = {"title", "category", "priority", "estimateMinutes"}


@router.post("/captures", response_model=CaptureResult)
def create_capture(
    payload: CaptureRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    The First Capture endpoint. Per System Architecture §11: capture + tasks
    returned in one response, no second round trip. Failure is a controlled,
    200-status outcome — not an HTTP error — since the request itself
    succeeded and the raw text was safely persisted either way (see the
    design-phase reasoning on why this isn't a 4xx/5xx).
    """
    provider = get_model_provider()
    result = run_extraction(db, current_user.id, payload.rawText, provider)

    return CaptureResult(
        capture=CaptureResponse.from_model(result.capture),
        tasks=[TaskResponse.from_model(t) for t in result.tasks],
        failureReason=result.failure_reason,
    )


@router.get("/tasks", response_model=list[TaskResponse])
def list_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """FR-3.1 — flat list, no nesting. Scoped strictly to the authenticated user."""
    tasks = db.query(Task).filter(Task.user_id == current_user.id).order_by(Task.created_at.desc()).all()
    return [TaskResponse.from_model(t) for t in tasks]


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    FR-3.3/FR-4.1/4.2/4.3 — manual editing of any field (including status,
    per FR-3.3) plus the Quiet Correction on AI-assigned fields specifically.
    One request, immediate effect, no confirmation semantics anywhere in
    this contract, no reactive/apologetic copy generated here (that's a
    frontend concern, but this endpoint doesn't return anything that would
    prompt it either).

    Writes a FieldCorrectionRecord per changed field ONLY when the task's
    origin is AIGenerated AND the field is one of the AI-assigned fields
    (Domain Model §10.3: CorrectionTracker is invoked "whenever a user
    changes an AI-assigned field"). `status` is deliberately excluded from
    this even on an AI-generated task — completing a task isn't a
    correction. This record is never included in this endpoint's response
    (BR-4).
    """
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    changes = payload.model_dump(exclude_unset=True)
    track_corrections = task.origin == TaskOrigin.AI_GENERATED

    for field_name, new_value in changes.items():
        # Map API field names to model attribute names where they differ.
        model_field = "estimate_minutes" if field_name == "estimateMinutes" else field_name
        old_value = getattr(task, model_field)

        # Normalize both sides to plain comparable values before comparing —
        # str(enum_member) is inconsistent across Python versions for
        # str-subclassed enums (sometimes "Low", sometimes "Priority.LOW"),
        # which would make this comparison unreliable and risk polluting the
        # internal correction-rate metric (Blueprint §17) with false positives.
        old_comparable = old_value.value if hasattr(old_value, "value") else old_value

        if (
            track_corrections
            and field_name in CORRECTION_TRACKED_FIELDS
            and old_comparable != new_value
        ):
            db.add(FieldCorrectionRecord(
                id=uuid.uuid4(),
                task_id=task.id,
                field_name=model_field,
                original_value=str(old_comparable) if old_comparable is not None else None,
                corrected_value=str(new_value) if new_value is not None else None,
            ))

        setattr(task, model_field, new_value)

    db.commit()
    db.refresh(task)
    return TaskResponse.from_model(task)