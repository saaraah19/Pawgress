import uuid
from datetime import date as date_type, datetime
from typing import Literal, Optional
from pydantic import BaseModel


class PlannerEntryResponse(BaseModel):
    id: uuid.UUID
    periodType: Literal["Week", "Month"]
    periodStart: date_type
    intention: Optional[str]
    reflection: Optional[str]
    updatedAt: datetime

    @classmethod
    def from_model(cls, entry) -> "PlannerEntryResponse":
        return cls(
            id=entry.id,
            periodType=entry.period_type.value,
            periodStart=entry.period_start,
            intention=entry.intention,
            reflection=entry.reflection,
            updatedAt=entry.updated_at,
        )


class PlannerEntryUpsertRequest(BaseModel):
    periodType: Literal["Week", "Month"]
    # Any date within the target period — the backend normalizes it to
    # that period's anchor (containing Sunday for Week, the 1st for
    # Month), same "don't make the client compute the exact boundary"
    # convenience as habits/routes.py's weekStart query param.
    periodStart: date_type
    # exclude_unset (not these being Optional) is what distinguishes "the
    # client didn't mention this field" from "the client explicitly wants
    # it cleared" — same pattern as ProfileUpdateRequest/HabitUpdateRequest.
    intention: Optional[str] = None
    reflection: Optional[str] = None
