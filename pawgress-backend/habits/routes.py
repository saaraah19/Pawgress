"""
habits/routes.py

CRUD for Habit + two small endpoints for the one thing that actually
changes moment to moment: marking a day complete, or undoing that. No
"missed" endpoint exists, on purpose — there is nothing to mark as missed
(habits/models.py's module docstring covers why).

Update consistency: same discipline established for Goal hierarchy
(productivity/routes.py's update_goal) — a partial update that would leave
`frequency`/`weeklyTarget` in an inconsistent state is rejected outright
(422, nothing persisted), never silently auto-corrected. If you change
frequency to "Daily" on a habit that has an existing weeklyTarget, you
must clear weeklyTarget explicitly in the same request; the endpoint
won't guess that for you.
"""

import uuid
from datetime import date as date_type
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from shared.database import get_db
from identity.auth import get_current_user
from identity.models import User
from productivity.models import Goal
from habits.models import Habit, HabitCompletion, HabitFrequency, today_utc
from habits.schemas import HabitCreateRequest, HabitUpdateRequest, HabitResponse

router = APIRouter(prefix="/habits", tags=["habits"])


def _validate_frequency_consistency(frequency: HabitFrequency, weekly_target: int | None) -> None:
    if frequency == HabitFrequency.WEEKLY_COUNT and weekly_target is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="weeklyTarget is required when frequency is 'WeeklyCount'.",
        )
    if frequency == HabitFrequency.DAILY and weekly_target is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="weeklyTarget must not be set when frequency is 'Daily' — clear it explicitly in this same request.",
        )


def _to_response(db: Session, habit: Habit) -> HabitResponse:
    total = db.query(HabitCompletion).filter(HabitCompletion.habit_id == habit.id).count()
    completed_today = (
        db.query(HabitCompletion)
        .filter(HabitCompletion.habit_id == habit.id, HabitCompletion.date == today_utc())
        .first()
        is not None
    )
    return HabitResponse.from_model(habit, total_completions=total, completed_today=completed_today)


@router.post("", response_model=HabitResponse, status_code=status.HTTP_201_CREATED)
def create_habit(
    payload: HabitCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.goalId is not None:
        goal = db.query(Goal).filter(Goal.id == payload.goalId, Goal.user_id == current_user.id).first()
        if not goal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")

    habit = Habit(
        id=uuid.uuid4(),
        user_id=current_user.id,
        label=payload.label.strip(),
        frequency=HabitFrequency(payload.frequency),
        weekly_target=payload.weeklyTarget,
        goal_id=payload.goalId,
    )
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return _to_response(db, habit)


@router.get("", response_model=list[HabitResponse])
def list_habits(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    habits = db.query(Habit).filter(Habit.user_id == current_user.id).order_by(Habit.created_at.desc()).all()
    return [_to_response(db, h) for h in habits]


@router.patch("/{habit_id}", response_model=HabitResponse)
def update_habit(
    habit_id: uuid.UUID,
    payload: HabitUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    habit = db.query(Habit).filter(Habit.id == habit_id, Habit.user_id == current_user.id).first()
    if not habit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found.")

    changes = payload.model_dump(exclude_unset=True)

    if "label" in changes:
        habit.label = changes["label"].strip()

    if "goalId" in changes:
        new_goal_id = changes["goalId"]
        if new_goal_id is not None:
            goal = db.query(Goal).filter(Goal.id == new_goal_id, Goal.user_id == current_user.id).first()
            if not goal:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found.")
        habit.goal_id = new_goal_id

    if "frequency" in changes or "weeklyTarget" in changes:
        new_frequency = HabitFrequency(changes["frequency"]) if "frequency" in changes else habit.frequency
        new_weekly_target = changes["weeklyTarget"] if "weeklyTarget" in changes else habit.weekly_target
        _validate_frequency_consistency(new_frequency, new_weekly_target)
        habit.frequency = new_frequency
        habit.weekly_target = new_weekly_target

    db.commit()
    db.refresh(habit)
    return _to_response(db, habit)


@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_habit(
    habit_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes the Habit and, via DB-level ON DELETE CASCADE, its
    completions — the one deliberate cascade-delete exception in this
    codebase (see habits/models.py's docstring for why that's the correct
    call here specifically, unlike everywhere else)."""
    habit = db.query(Habit).filter(Habit.id == habit_id, Habit.user_id == current_user.id).first()
    if not habit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found.")
    db.delete(habit)
    db.commit()


@router.post("/{habit_id}/completions", response_model=HabitResponse, status_code=status.HTTP_201_CREATED)
def mark_habit_complete(
    habit_id: uuid.UUID,
    completion_date: date_type | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Records a positive completion for the given date (defaults to
    today). Marking an already-completed date again is a harmless no-op
    (idempotent), not an error — a double-tap shouldn't need special
    handling on either the client or here."""
    habit = db.query(Habit).filter(Habit.id == habit_id, Habit.user_id == current_user.id).first()
    if not habit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found.")

    target_date = completion_date or today_utc()
    existing = (
        db.query(HabitCompletion)
        .filter(HabitCompletion.habit_id == habit.id, HabitCompletion.date == target_date)
        .first()
    )
    if not existing:
        db.add(HabitCompletion(id=uuid.uuid4(), habit_id=habit.id, date=target_date))
        db.commit()

    return _to_response(db, habit)


@router.delete("/{habit_id}/completions/{completion_date}", response_model=HabitResponse)
def unmark_habit_complete(
    habit_id: uuid.UUID,
    completion_date: date_type,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Undoes a completion — e.g. a misclick. This removes a positive
    record; it does NOT create a 'missed' record of any kind (there is no
    such thing in this schema)."""
    habit = db.query(Habit).filter(Habit.id == habit_id, Habit.user_id == current_user.id).first()
    if not habit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found.")

    db.query(HabitCompletion).filter(
        HabitCompletion.habit_id == habit.id, HabitCompletion.date == completion_date
    ).delete()
    db.commit()

    return _to_response(db, habit)
