"""
planner/models.py

Weekly/Monthly Planner (2026-09-15) — a new, deliberately small concept:
"what am I focusing on this period" (intention) plus "how did it go"
(reflection), one entry per user per calendar period. Kept structurally
separate from Goal on purpose (Sarah's explicit call, not a technical
default): Goals are enduring structure a user builds over time and never
expire; a PlannerEntry is a recurring ritual container that resets every
week/month. Conflating the two would make Goals mean two different things
depending on context, which is exactly the kind of ambiguity Domain
Model's "reference, don't embed" discipline exists to avoid. No FK to
Goal at all — intentionally fully independent (explicit product decision,
not an oversight).

Both `intention` and `reflection` are plain, freely-editable text, and
BOTH are always editable regardless of where you are in the period — set
your intention early, revise it mid-week, write your reflection whenever
you get to it, or fill in both at once looking back. There is no locking,
no "you can't reflect until the period ends" gate. Imposing artificial
timing rules here would be exactly the kind of manual-system-maintenance
burden the whole product exists to remove (MVP Definition §3), for a
feature whose entire value is being a lightweight, low-friction ritual.

No completion tracking, no streak of "did you fill this in every period"
— that would quietly become the same shame mechanic the rest of this
product has structurally banned (Blueprint §16, FR-6.2's spirit extended
here). A period with nothing written in it is simply a period with
nothing written in it, exactly as valid as one that is.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Text, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from shared.database import Base


class PlannerPeriodType(str, enum.Enum):
    WEEK = "Week"
    MONTH = "Month"


class PlannerEntry(Base):
    __tablename__ = "planner_entries"
    __table_args__ = (
        # One entry per user per period — "period_start" is the anchor
        # date identifying which week/month this is (the Sunday for a
        # Week entry, the 1st for a Month entry), so this constraint is
        # what makes an upsert-by-period well-defined rather than
        # accumulating duplicate rows for the same period.
        UniqueConstraint("user_id", "period_type", "period_start", name="uq_planner_entry_period"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    period_type = Column(
        Enum(PlannerPeriodType, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    # Sunday-start for Week (matching habits/routes.py's convention
    # exactly, so the two features never disagree about what "this week"
    # means), the 1st of the month for Month. A plain calendar Date, not
    # a DateTime — a period is a whole day-granularity concept, not a
    # specific moment.
    period_start = Column(Date, nullable=False, index=True)
    intention = Column(Text, nullable=True)
    reflection = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
