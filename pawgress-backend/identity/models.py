"""
identity/models.py

The User aggregate root. Per Domain Model §4.1: "the anchor for all ownership" —
every other entity in the system references a User by ID, never the reverse.

Deliberately minimal, per FR-1.3 and the Handover's framing of auth as
"infrastructure, not a growth surface." No profile fields beyond what's needed
to authenticate and display a neutral name.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID

from shared.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    # Nullable, not required — FR-1.3: "defaults to a neutral placeholder if not
    # provided," never a blank/required field. The neutral default itself is
    # applied at the API layer (see identity/schemas.py), not stored as a fake
    # value here — this column being NULL *is* "no display name set yet."
    display_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
