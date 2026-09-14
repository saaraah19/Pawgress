"""
productivity/routes.py

FR-2.x (AI Inbox capture), FR-3.x (task list/editing/manual creation/deletion),
FR-4.x (one-tap correction), FR-5.x (goal creation and linking).

Authorization rule applied consistently, per System Architecture §9: every
query/mutation here is scoped by the authenticated user's ID as a non-optional
parameter — never an afterthought filter.
"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from shared.database import get_db
from identity.auth import get_current_user
from identity.models import User
from productivity.models import Task, Goal, FieldCorrectionRecord, TaskOrigin, TaskStatus, Priority, GoalTier
from productivity.schemas import (
    CaptureRequest,
    CaptureResult,
    CaptureResponse,
    TaskResponse,
    TaskUpdateRequest,
    ManualTaskCreateRequest,
    GoalCreateRequest,
    GoalUpdateRequest,
    GoalResponse,
)
from productivity.extraction_service import run_extraction
from productivity.goal_service import delete_goal_and_unlink_references, validate_parent_link, InvalidGoalParentError
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


# Voice capture (2026-09-13) — a real, approved V2 feature (Engineering
# Handover §4: "pulled forward from 'someday' to early Version 2... typing
# a paragraph is still real friction against a 'just talk to it' pitch"),
# not a stub. A generous but bounded upload size — short personal voice
# notes, not long-form audio, so this is a cost/abuse guard (System
# Architecture §17) matching CaptureRequest's own max_length reasoning,
# not a product constraint anyone is expected to bump into normally.
MAX_AUDIO_UPLOAD_BYTES = 15 * 1024 * 1024  # ~15MB, comfortably more than a few minutes of compressed speech


@router.post("/captures/transcribe")
async def transcribe_capture_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Deliberately separate from POST /captures, not a variant of it — this
    endpoint's ONLY job is turning audio into text and handing it back for
    the user to see and edit, exactly like something they'd typed
    themselves. It does NOT create a Capture or call extraction.

    This split is a direct, deliberate response to MVP Definition §5's own
    caution about voice: "it introduces transcription accuracy and latency
    variables that would muddy the MVP's central test." Routing the
    transcript back through the same textarea a typed capture would use
    means a misheard word is exactly as cheap to fix as a typo would be —
    UX Philosophy §5.2's Quiet Correction philosophy, extended to
    transcription errors rather than just AI-extraction errors — and the
    user, not this endpoint, decides when what's on screen is ready to
    actually submit as a capture.
    """
    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="That recording is too long. Try a shorter note, or type it instead.",
        )
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No audio was received.")

    provider = get_model_provider()
    result = provider.transcribe_audio(audio_bytes, filename=file.filename or "recording.webm")

    if result.outcome != "success":
        # A controlled, honest failure — same philosophy as extraction's
        # schema_invalid/provider_error handling (System Architecture §20):
        # the user always has the manual fallback (just type it) sitting
        # right there, so this never blocks capture, it just doesn't help
        # this once.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't transcribe that recording. You can type it instead.",
        )

    return {"text": result.text}


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

        # Wistful mood tier (companion/mood_calculator.py): track the most
        # recent completion EVENT, not just current status. Un-completing
        # honestly clears the signal rather than leaving a stale timestamp
        # that would make an undone completion still count toward "not
        # wistful" — completed_at means "completed," full stop.
        if field_name == "status":
            task.completed_at = datetime.now(timezone.utc) if new_value == TaskStatus.DONE.value else None

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
    """FR-5.1, extended for V2 hierarchy. `tier` is optional — omitting it
    creates a flat MVP-style goal exactly as before. No `parentGoalId`
    accepted at creation (see GoalCreateRequest's docstring) — assigning a
    parent is a deliberate follow-up action via PATCH."""
    goal = Goal(
        id=uuid.uuid4(),
        user_id=current_user.id,
        label=payload.label.strip(),
        tier=GoalTier(payload.tier) if payload.tier else None,
    )
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


@router.patch("/goals/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: uuid.UUID,
    payload: GoalUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """FR-5.1 (label editing) extended for V2 hierarchy: assigning/changing
    `tier` and `parentGoalId` both happen here, one field at a time or
    together, no confirmation step (same one-tap-correction shape as
    update_task). This is the endpoint that lets a user "earn" hierarchy on
    an existing flat goal — tier and parent were deliberately not accepted
    at creation time.

    Parent validation mirrors the existing Task.goalId cross-user check
    (Domain Model Invariant 3) plus the new tier-ordering rule
    (goal_service.validate_parent_link) — both enforced here, not left to
    the database, consistent with ADR 0001's reasoning for keeping domain
    invariants in application code.

    IMPORTANT: a tier change alone (parentGoalId not touched in this same
    request) can silently invalidate an EXISTING parent or child link if
    left unchecked — e.g. a Milestone re-tiered to Annual while still
    parented under another Annual goal would violate "parent must be
    strictly broader" without either field looking wrong in isolation.
    So whenever tier changes, every existing parent/child edge touching
    this goal is re-validated against the new tier before committing;
    the whole request is rejected (422, nothing persisted) rather than
    silently leaving the tree in an inconsistent state or silently
    unlinking something the user didn't ask to unlink.
    """
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")

    changes = payload.model_dump(exclude_unset=True)

    if "label" in changes:
        goal.label = changes["label"].strip()

    if "tier" in changes:
        goal.tier = GoalTier(changes["tier"]) if changes["tier"] else None

    if "parentGoalId" in changes:
        new_parent_id = changes["parentGoalId"]
        if new_parent_id is None:
            goal.parent_goal_id = None
        else:
            parent = db.query(Goal).filter(Goal.id == new_parent_id, Goal.user_id == current_user.id).first()
            if not parent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent goal not found.")
            try:
                validate_parent_link(goal, parent)
            except InvalidGoalParentError as e:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.reason)
            goal.parent_goal_id = parent.id

    if "tier" in changes:
        # Re-validate every existing edge this goal participates in against
        # its (possibly just-changed) tier — see the docstring above for why.
        # Skips the parent edge if this same request already touched
        # parentGoalId (already validated, or intentionally cleared, above).
        if goal.parent_goal_id is not None and "parentGoalId" not in changes:
            current_parent = db.query(Goal).filter(Goal.id == goal.parent_goal_id).first()
            try:
                validate_parent_link(goal, current_parent)
            except InvalidGoalParentError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Changing this goal's tier to {goal.tier.value if goal.tier else 'none'} would make "
                        f"its current parent an invalid tier for it. Unlink or re-tier the parent first."
                    ),
                )

        children = db.query(Goal).filter(Goal.parent_goal_id == goal.id).all()
        for child in children:
            try:
                validate_parent_link(child, goal)
            except InvalidGoalParentError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Changing this goal's tier to {goal.tier.value if goal.tier else 'none'} would make "
                        f"it an invalid parent for '{child.label}'. Unlink or re-tier that child first."
                    ),
                )

    db.commit()
    db.refresh(goal)
    return GoalResponse.from_model(goal)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Domain Model §10.5/Invariant 9 — unlink, never cascade. Extended for
    hierarchy: child Goals are unlinked exactly like Tasks are. See
    goal_service.py."""
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")
    delete_goal_and_unlink_references(db, goal)
