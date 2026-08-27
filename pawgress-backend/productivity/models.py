"""
productivity/models.py

The three entities that make up this slice's core: Capture, Task, and the
internal-only FieldCorrectionRecord. Traced directly to Domain Model §4.2, §4.4,
and §5.1 — no new entities invented here.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID

from shared.database import Base


class CaptureStatus(str, enum.Enum):
    """Domain Model §7. Exactly these three values — a Failed capture still
    exists as a record, with raw text intact (FR-2.7's manual-fallback path
    needs something to act on)."""
    PENDING = "Pending"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"


class TaskStatus(str, enum.Enum):
    """FR-3.2: exactly two states. No 'InProgress' — resist adding it "for
    completeness," per Domain Model §7's explicit warning."""
    NOT_STARTED = "NotStarted"
    DONE = "Done"


class Priority(str, enum.Enum):
    """Domain Model §7 — a simple three-value enum, the least-assumption-making
    choice available."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class TaskOrigin(str, enum.Enum):
    """Domain Model §7 / Modeling Principle 3 — internal provenance metadata
    ONLY. Never a permission gate, never shown as a badge implying an
    AI-generated task is less "owned" than a manual one (Domain Model §11)."""
    AI_GENERATED = "AIGenerated"
    MANUALLY_CREATED = "ManuallyCreated"


class GoalTier(str, enum.Enum):
    """V2 goal hierarchy (Blueprint §13): Annual -> Quarterly -> Project ->
    Milestone, in strictly decreasing order of scope. A Goal's tier is
    OPTIONAL (see Goal.tier below) — assigning one is how a user opts into
    hierarchy at all, per Domain Model §4.3's "the system earns hierarchy,
    it doesn't assume it." Ordinal position in this list is meaningful and
    is what goal_service.py's parent/child validation compares against —
    do not reorder without updating that comparison."""
    ANNUAL = "Annual"
    QUARTERLY = "Quarterly"
    PROJECT = "Project"
    MILESTONE = "Milestone"


# Ordinal rank per tier — lower number = broader scope. Used by
# goal_service.py to enforce "a parent must be a strictly higher tier than
# its child," which is also what makes a hierarchy cycle structurally
# impossible (a chain of strictly-decreasing ranks can never loop back).
GOAL_TIER_RANK: dict[GoalTier, int] = {tier: rank for rank, tier in enumerate(GoalTier)}


class Capture(Base):
    """Domain Model §4.4 — permanent, retained record from day one, even though
    no MVP UI currently surfaces "your capture history." raw_text is immutable
    once written: no code path in this module updates it after INSERT."""
    __tablename__ = "captures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    raw_text = Column(Text, nullable=False)
    # values_callable: store/match by the enum's VALUE ("Pending", not "PENDING") —
    # SQLAlchemy's default behavior matches by member NAME, which would silently
    # reject plain-string assignments like "Pending" since the member name is
    # "PENDING". This matters wherever a route handler assigns a raw string
    # (see productivity/routes.py's update_task) rather than an enum instance.
    status = Column(Enum(CaptureStatus, values_callable=lambda x: [e.value for e in x]),
                     nullable=False, default=CaptureStatus.PENDING)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Goal(Base):
    """Domain Model §4.3, extended for V2 hierarchy (Blueprint §13).

    MVP behavior is fully preserved for anyone who doesn't engage with
    hierarchy: `tier` and `parent_goal_id` are both nullable, and a Goal
    with tier=NULL behaves exactly like the original flat MVP Goal — a
    single label, no structure. Assigning a tier is how a user opts into
    hierarchy at all (Domain Model §4.3: "the system earns hierarchy, it
    doesn't assume it") — this is enforced at the schema level, not just
    in the UI: `parent_goal_id` may only be set when both this Goal and
    its proposed parent already have a tier (see goal_service.py), so an
    untiered goal can neither have a parent nor be one.

    parent_goal_id: nullable, self-referential, single-valued (a Goal has
    at most one parent — this is a tree, not a general graph). No DB-level
    ON DELETE CASCADE or SET NULL, same reasoning as Task.goal_id below and
    ADR 0001's Decision 1: unlinking children when a Goal is deleted is
    handled explicitly by goal_service.py, so the invariant lives in one
    deliberate, testable function rather than implicit DDL that could stay
    "accidentally correct" only until some other code path deletes a row.
    """
    __tablename__ = "goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    label = Column(String, nullable=False)
    tier = Column(Enum(GoalTier, values_callable=lambda x: [e.value for e in x]), nullable=True)
    parent_goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Task(Base):
    """Domain Model §4.2 — the atomic unit of "something the user intends to do."

    goal_id: optional, single-valued reference to Goal (FR-5.2, Domain Model
    §8). Nullable FK, no ON DELETE CASCADE — deletion is handled explicitly by
    GoalDeletionService (goal_service.py) per Domain Model §10.5 / Invariant 9:
    deleting a Goal unlinks referencing Tasks, it never deletes them. A DB-level
    CASCADE would silently violate that invariant if anything ever deleted a
    Goal by a path other than the service, so the unlink is done in application
    code instead of relying on ON DELETE SET NULL.

    category is nullable — AC-3.4.1: a manually-created task may leave
    category unset entirely rather than having one inferred. AI-extracted
    tasks always populate it (ExtractionService always returns a category),
    so this relaxation only actually matters for the manual-creation path.
    """
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=True)  # free text, per Domain Model §6's
    # resolved decision — never a constrained taxonomy; nullable per AC-3.4.1
    priority = Column(Enum(Priority, values_callable=lambda x: [e.value for e in x]),
                       nullable=False, default=Priority.MEDIUM)
    estimate_minutes = Column(Integer, nullable=True)  # nullable — see Domain
    # Model §6 TimeEstimate value object; null means genuinely not inferable,
    # never a placeholder for "didn't bother"
    status = Column(Enum(TaskStatus, values_callable=lambda x: [e.value for e in x]),
                     nullable=False, default=TaskStatus.NOT_STARTED)
    origin = Column(Enum(TaskOrigin, values_callable=lambda x: [e.value for e in x]),
                     nullable=False)
    source_capture_id = Column(UUID(as_uuid=True), ForeignKey("captures.id"), nullable=True, index=True)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class FieldCorrectionRecord(Base):
    """Domain Model §5.1 — internal-only. Written whenever a user corrects an
    AI-assigned field. Explicit constraint (Domain Model Invariant 7, BR-4):
    this must NEVER be joined into, or exposed through, any user-facing API
    response. Its only consumer is internal metrics — no route in this codebase
    reads from this table for anything the client sees."""
    __tablename__ = "field_correction_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    field_name = Column(String, nullable=False)  # e.g. "category", "priority", "estimate_minutes", "title"
    original_value = Column(String, nullable=True)
    corrected_value = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
