"""
journal/models.py

Domain Model §13: "JournalEntry — Version 2. A distinct capture surface
with its own emotional-design considerations; not an extension of Capture,
since journaling and task-extraction are different intents even though
both start as natural language."

That separation is enforced structurally here, not just in naming:
JournalEntry lives in its own module, has no foreign key to Capture, Task,
or Goal, and nothing in this module ever calls into ai_extraction. A
journal entry is never turned into structure — it stays exactly what the
user wrote, for as long as they keep it.

Aggregate root, same shape-of-reasoning as Capture (Domain Model §4.4):
owned by exactly one User, permanent by default, deletable independently
of everything else in the system (Modeling Principle 1 and 5 — small,
independently loadable/editable/deletable aggregates).

One deliberate departure from Capture's design, worth naming explicitly:
`text` is NOT immutable. Capture's raw_text immutability (Domain Model
Invariant 4) exists specifically to protect extraction provenance — there
is no extraction here to protect, and a journal entry is much closer in
spirit to something a user should be able to refine (fix a typo, add a
line) than to an audit-trail record. This is a judgment call, not a
literal document requirement; if that turns out to be wrong, it's a
one-line change (drop the PATCH endpoint), not a schema migration.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from shared.database import Base


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
