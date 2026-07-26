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


class Task(Base):
    """Domain Model §4.2 — the atomic unit of "something the user intends to do."
    goal_id deliberately NOT included as a column yet — Domain Model Modeling
    Principle 6 ("when in doubt, don't model it yet"); Sarah's explicit call
    during the Slice 1 design discussion. Added when the Goals slice is built."""
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)  # free text, per Domain Model §6's
    # resolved decision — never a constrained taxonomy
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
