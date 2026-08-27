"""
habits/schemas.py — request/response shapes for the Habits module.
"""

import uuid
from datetime import datetime, date as date_type
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


class HabitCreateRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    frequency: Literal["Daily", "WeeklyCount"]
    # Required exactly when frequency == "WeeklyCount", forbidden otherwise —
    # validated below rather than left to accidentally-inconsistent data.
    weeklyTarget: Optional[int] = Field(None, ge=1, le=7)
    goalId: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def check_weekly_target_consistency(self) -> "HabitCreateRequest":
        if self.frequency == "WeeklyCount" and self.weeklyTarget is None:
            raise ValueError("weeklyTarget is required when frequency is 'WeeklyCount'.")
        if self.frequency == "Daily" and self.weeklyTarget is not None:
            raise ValueError("weeklyTarget must not be set when frequency is 'Daily'.")
        return self


class HabitUpdateRequest(BaseModel):
    """Every field optional, same one-tap-correction shape used throughout
    (TaskUpdateRequest, GoalUpdateRequest). `frequency` and `weeklyTarget`
    are cross-validated together only when at least one of them is present
    in the same request — changing just the label, for instance, shouldn't
    require re-stating the frequency."""
    label: Optional[str] = Field(None, min_length=1, max_length=200)
    frequency: Optional[Literal["Daily", "WeeklyCount"]] = None
    weeklyTarget: Optional[int] = Field(None, ge=1, le=7)
    goalId: Optional[uuid.UUID] = None


class HabitCompletionResponse(BaseModel):
    date: date_type


class HabitResponse(BaseModel):
    id: uuid.UUID
    label: str
    frequency: Literal["Daily", "WeeklyCount"]
    weeklyTarget: Optional[int]
    goalId: Optional[uuid.UUID]
    # Progress signal, deliberately not a streak (see models.py docstring):
    # a plain lifetime count that only ever grows.
    totalCompletions: int
    completedToday: bool
    createdAt: datetime

    @classmethod
    def from_model(cls, habit, total_completions: int, completed_today: bool) -> "HabitResponse":
        return cls(
            id=habit.id,
            label=habit.label,
            frequency=habit.frequency.value,
            weeklyTarget=habit.weekly_target,
            goalId=habit.goal_id,
            totalCompletions=total_completions,
            completedToday=completed_today,
            createdAt=habit.created_at,
        )
