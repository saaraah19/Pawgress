"""
gamification/routes.py

One endpoint, deliberately: everything here is read-only and computed —
there is nothing to create, update, or delete, because there is no
persisted gamification state at all (see catalog.py's docstring). This
also means there is no way for this module to ever get out of sync with
the Task/Habit data it reflects — it's recomputed fresh on every request,
the same freshness guarantee companion mood already has.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from shared.database import get_db
from identity.auth import get_current_user
from identity.models import User
from productivity.models import Task, TaskStatus
from habits.models import HabitCompletion, Habit
from gamification.catalog import (
    XP_PER_COMPLETION,
    xp_for_level,
    level_for_xp,
    unlocked_items,
    UNLOCKABLE_ITEMS,
)
from gamification.schemas import GamificationStateResponse, UnlockableItemResponse

router = APIRouter(prefix="/gamification", tags=["gamification"])


@router.get("/state", response_model=GamificationStateResponse)
def get_gamification_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task_completions = (
        db.query(func.count(Task.id))
        .filter(Task.user_id == current_user.id, Task.status == TaskStatus.DONE)
        .scalar()
        or 0
    )
    habit_completions = (
        db.query(func.count(HabitCompletion.id))
        .join(Habit, HabitCompletion.habit_id == Habit.id)
        .filter(Habit.user_id == current_user.id)
        .scalar()
        or 0
    )

    completions = task_completions + habit_completions
    xp = completions * XP_PER_COMPLETION
    level = level_for_xp(xp)

    unlocked_ids = {item.id for item in unlocked_items(level)}
    items = [
        UnlockableItemResponse(
            id=item.id,
            kind=item.kind,
            name=item.name,
            description=item.description,
            unlockLevel=item.unlockLevel,
            unlocked=item.id in unlocked_ids,
        )
        for item in UNLOCKABLE_ITEMS
    ]

    return GamificationStateResponse(
        completions=completions,
        xp=xp,
        level=level,
        xpForCurrentLevel=xp_for_level(level),
        xpForNextLevel=xp_for_level(level + 1),
        items=items,
    )
