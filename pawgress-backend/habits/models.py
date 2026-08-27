"""
habits/models.py

V2 Habits (Blueprint §13), with the specific design constraint the docs
call out directly: a traditional streak counter is exactly the mechanic
Blueprint §16 names as suspect — "proven precisely because it works
through mild guilt, which this product has explicitly ruled out." This
module does not implement a streak in the conventional sense at all.

Three governing decisions (made explicitly, not defaulted into):

1. Progress is an ACCUMULATING TOTAL that never resets — the same
   principle already locked in for the companion's future growth model
   (companion-character-spec.md §5.E: "growth reflects accumulated
   progress, never daily performance... a missed task or a bad day must
   never shrink [it]"), applied here to Habits. There is no "current
   streak" field anywhere in this schema, and no code path computes one.
2. Scheduling is per-habit, not forced into one shape (Daily or a
   flexible weekly count) — same "don't force rigidity" reasoning as
   Category staying free text instead of a constrained taxonomy
   (Domain Model §6).
3. Missed days are NEVER recorded, anywhere, not even internally. This
   module only knows how to store positive completion events
   (HabitCompletion). There is no "missed" row, no absence flag, no
   computed gap — silence really is silence here, structurally, not just
   in what's displayed (direct extension of FR-6.2/Blueprint §4's
   "silence is a valid design choice" to a new domain, at the schema
   level rather than only the presentation level).

HabitCompletion is a genuinely owned child of Habit, unlike Task/Goal's
independent-aggregate relationship (Domain Model §2's "reference, don't
embed" governs Task<->Goal specifically because a Task must remain
meaningful — and independently deletable — even if its linked Goal is
gone). A completion record has no meaning independent of the habit it
completed; there is no future-memory or provenance reason to retain
orphaned completions the way Capture is retained independent of its
Tasks. So, unlike every other cross-entity relationship in this codebase,
deleting a Habit DOES cascade to its completions at the database level
(ON DELETE CASCADE) — a deliberate, narrow exception, not an oversight or
a drift from the established "unlink, don't cascade" pattern.
"""

import enum
import uuid
from datetime import datetime, timezone, date as date_type

from sqlalchemy import Column, String, DateTime, Date, Integer, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from shared.database import Base


class HabitFrequency(str, enum.Enum):
    DAILY = "Daily"
    WEEKLY_COUNT = "WeeklyCount"


class Habit(Base):
    """Aggregate root. `weekly_target` is only meaningful when
    frequency == WeeklyCount (validated at the schema layer, habits/schemas.py)
    — kept nullable here rather than modeled as two separate tables, since
    it's one small piece of metadata, not a structurally different entity.

    `goal_id` is optional, single-valued, same pattern as Task.goal_id —
    no DB cascade (a Habit must remain independently deletable/meaningful
    even if its linked Goal is later removed; see productivity/goal_service.py
    for the exact precedent this mirrors)."""
    __tablename__ = "habits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    label = Column(String, nullable=False)
    frequency = Column(Enum(HabitFrequency, values_callable=lambda x: [e.value for e in x]), nullable=False)
    weekly_target = Column(Integer, nullable=True)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class HabitCompletion(Base):
    """A single positive completion event for one calendar day. `date`
    (not a timestamp) because a habit is completed *on a day*, not at a
    precise instant — matches the UTC-calendar-day simplification already
    used and documented in companion/mood_calculator.py (doesn't respect
    the user's local timezone yet; acceptable now, cheap to fix later,
    same reasoning).

    Unique on (habit_id, date): at most one completion per habit per day —
    mirrors Task's exactly-two-states precedent (binary, not quantity-
    tracked) applied to a day rather than a task."""
    __tablename__ = "habit_completions"
    __table_args__ = (UniqueConstraint("habit_id", "date", name="uq_habit_completion_day"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    habit_id = Column(UUID(as_uuid=True), ForeignKey("habits.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def today_utc() -> date_type:
    """Single source of truth for "today," so every call site agrees —
    same UTC-calendar-day approach as companion/mood_calculator.py."""
    return datetime.now(timezone.utc).date()
