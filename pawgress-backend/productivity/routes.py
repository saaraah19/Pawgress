"""
productivity/routes.py

FR-2.x (AI Inbox capture), FR-3.x (task list/editing/manual creation/deletion),
FR-4.x (one-tap correction), FR-5.x (goal creation and linking).

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
from productivity.models import Task, Goal, FieldCorrectionRecord, TaskOrigin, Priority
from productivity.schemas import (
    CaptureRequest,
    CaptureResult,
    CaptureResponse,
    TaskResponse,
    TaskUpdateRequest,
    ManualTaskCreateRequest,
    GoalCreateRequest,
    GoalResponse,
)
from productivity.extraction_service import run_extraction
from productivity.goal_service import delete_goal_and_unlink_tasks
from ai_extraction.provider import get_model_provider

router = APIRouter(tags=["productivity"])

# FR-4/BR-4 govern corrections on AI-ASSIGNED fields specifically — status
# and goalId are excluded on purpose. Marking a task Done is the ordinary
# Completing-and-Reflecting interaction (UX Philosophy §5.3), and linking a
# goal is the Discovering Goal-Linking interaction (UX Philosophy §5.4) —
# neither is "the AI got this wrong," so neither writes a FieldCorrectionRecord
# or counts toward the correction-rate metric (Blueprint §17).
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


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: ManualTaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    FR-3.4 — direct task creation, bypassing the AI Inbox. Per AC-3.4.1: a
    default NotStarted status, origin=ManuallyCreated, no source_capture_id,
    and no AI-assigned fields inferred — category/priority/estimate are
    exactly what the user provided (or left unset), never guessed.

    No FieldCorrectionRecord is ever written here — CorrectionTracker fires
    only when a user changes an *AI-assigned* field on an existing task
    (Domain Model §10.3); a field being set at manual-creation time was never
    an AI assignment to begin with, so there's nothing to "correct."
    """
    task = Task(
        id=uuid.uuid4(),
        user_id=current_user.id,
        title=payload.title.strip(),
        category=payload.category.strip() if payload.category else None,
        priority=Priority(payload.priority) if payload.priority else Priority.MEDIUM,
        estimate_minutes=payload.estimateMinutes,
        origin=TaskOrigin.MANUALLY_CREATED,
        source_capture_id=None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return TaskResponse.from_model(task)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    FR-3.3/FR-4.1/4.2/4.3/FR-5.2 — manual editing of any field (including
    status, per FR-3.3, and goalId, per FR-5.2) plus the Quiet Correction on
    AI-assigned fields specifically. One request, immediate effect, no
    confirmation semantics anywhere in this contract, no reactive/apologetic
    copy generated here (that's a frontend concern, but this endpoint doesn't
    return anything that would prompt it either).

    Writes a FieldCorrectionRecord per changed field ONLY when the task's
    origin is AIGenerated AND the field is one of the AI-assigned fields
    (Domain Model §10.3). `status` and `goalId` are deliberately excluded
    even on an AI-generated task — neither is a correction. This record is
    never included in this endpoint's response (BR-4).

    goalId cross-user linking check: Domain Model Invariant 3 — "A Task may
    be linked to at most one Goal, and that Goal must belong to the same User
    as the Task. Cross-user linking is invalid under any circumstance."
    """
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    changes = payload.model_dump(exclude_unset=True)

    if "goalId" in changes and changes["goalId"] is not None:
        goal = db.query(Goal).filter(Goal.id == changes["goalId"], Goal.user_id == current_user.id).first()
        if not goal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")

    track_corrections = task.origin == TaskOrigin.AI_GENERATED

    for field_name, new_value in changes.items():
        # Map API field names to model attribute names where they differ.
        model_field = {"estimateMinutes": "estimate_minutes", "goalId": "goal_id"}.get(field_name, field_name)
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


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    FR-3.5 — permanent deletion, regardless of AI or manual origin (full
    CRUD ownership, Domain Model §11). No confirmation dialog is enforced
    server-side (AC-3.5.1) — that's a client-side interaction decision, not
    an API contract concern. Source Capture is untouched (Domain Model
    Invariant 5 / Modeling Principle 1 — Task and Capture are independently
    deletable), and no FieldCorrectionRecord cleanup is needed here since
    those rows reference task_id with no FK-enforced cascade in this schema;
    they're internal-only records with no user-facing exposure regardless
    (BR-4) and are swept up wholesale on full account deletion (BR-10), not
    a per-task-deletion concern.
    """
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    db.delete(task)
    db.commit()


@router.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """FR-5.1 — a goal is a flat text label, nothing else."""
    goal = Goal(id=uuid.uuid4(), user_id=current_user.id, label=payload.label.strip())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return GoalResponse.from_model(goal)


@router.get("/goals", response_model=list[GoalResponse])
def list_goals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goals = db.query(Goal).filter(Goal.user_id == current_user.id).order_by(Goal.created_at.desc()).all()
    return [GoalResponse.from_model(g) for g in goals]


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Domain Model §10.5/Invariant 9 — unlink, never cascade. See goal_service.py."""
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")
    delete_goal_and_unlink_tasks(db, goal)
