"""
planner/routes.py

Two endpoints only, deliberately: fetch the entry for a given period (or
a well-defined "nothing yet" response, not a 404 — an unset period is a
normal, expected state, not an error), and upsert it. No delete endpoint:
clearing both fields via the upsert (empty strings -> None) is the
correct way to "remove" an entry's content, and the row itself existing
with nothing in it is harmless — there's no list-all-entries surface
where an empty row would clutter anything (FR/BR precedent: this mirrors
Habits/Journal's "no confirmation dialog needed" friction philosophy,
just taken one step further since there's nothing destructive to confirm
in the first place).
"""

import uuid
from datetime import date as date_type
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from shared.database import get_db
from identity.auth import get_current_user
from identity.models import User
from planner.models import PlannerEntry, PlannerPeriodType
from planner.schemas import PlannerEntryResponse, PlannerEntryUpsertRequest

router = APIRouter(prefix="/planner", tags=["planner"])


def _week_start_of(d: date_type) -> date_type:
    """Identical convention to habits/routes.py's helper of the same name
    — Sunday-start week, so Habits and Planner never disagree about what
    "this week" means. Duplicated rather than imported across modules on
    purpose: it's three lines, and importing across these module
    boundaries for a three-line date helper isn't worth the coupling
    (System Architecture §3's module-boundary discipline)."""
    from datetime import timedelta

    offset = (d.weekday() + 1) % 7
    return d - timedelta(days=offset)


def _month_start_of(d: date_type) -> date_type:
    return d.replace(day=1)


def _normalize_period_start(period_type: PlannerPeriodType, period_start: date_type) -> date_type:
    if period_type == PlannerPeriodType.WEEK:
        return _week_start_of(period_start)
    return _month_start_of(period_start)


@router.get("", response_model=PlannerEntryResponse | None)
def get_planner_entry(
    periodType: str = Query(...),
    periodStart: date_type = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns null (not a 404) when nothing has been written for this
    period yet — an unset period is a normal, expected state, not an
    error the client needs to handle specially."""
    resolved_type = PlannerPeriodType(periodType)
    normalized_start = _normalize_period_start(resolved_type, periodStart)

    entry = (
        db.query(PlannerEntry)
        .filter(
            PlannerEntry.user_id == current_user.id,
            PlannerEntry.period_type == resolved_type,
            PlannerEntry.period_start == normalized_start,
        )
        .first()
    )
    return PlannerEntryResponse.from_model(entry) if entry else None


@router.put("", response_model=PlannerEntryResponse)
def upsert_planner_entry(
    payload: PlannerEntryUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolved_type = PlannerPeriodType(payload.periodType)
    normalized_start = _normalize_period_start(resolved_type, payload.periodStart)

    entry = (
        db.query(PlannerEntry)
        .filter(
            PlannerEntry.user_id == current_user.id,
            PlannerEntry.period_type == resolved_type,
            PlannerEntry.period_start == normalized_start,
        )
        .first()
    )

    changes = payload.model_dump(exclude_unset=True)

    if not entry:
        entry = PlannerEntry(
            id=uuid.uuid4(),
            user_id=current_user.id,
            period_type=resolved_type,
            period_start=normalized_start,
        )
        db.add(entry)

    if "intention" in changes:
        entry.intention = changes["intention"] or None
    if "reflection" in changes:
        entry.reflection = changes["reflection"] or None

    db.commit()
    db.refresh(entry)
    return PlannerEntryResponse.from_model(entry)
