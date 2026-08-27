"""
calendar_integration/models.py

V2 Calendar integration (Blueprint §13), read-only v1 (Sarah's explicit
scope, 2026-08-19): Google Calendar -> Pawgress only. No writes back to
Google. No relationship of any kind to Task/Goal/Habit — Domain Model
§4.2's deliberate exclusion of scheduling/due-date fields from Task stays
fully intact; this module never imports from productivity/ or habits/.

One connection per user (`user_id` is unique) — connecting again replaces
the existing connection, per the approved scope. No multi-account support
in v1.

Security note on `refresh_token`, recorded explicitly rather than decided
silently: per product decision (2026-08-19), this relies on the existing
DB-level encryption-at-rest baseline (System Architecture §17) rather than
adding a new application-level encryption layer with its own key-
management story. This was presented to Sarah as a real security
tradeoff before building, not assumed — if that decision changes later,
only this model and google_provider.py's read/write of the field need to
change, not the API shape.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from shared.database import Base


class CalendarConnection(Base):
    __tablename__ = "calendar_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    # Plain string, not an enum — Google is the only provider in v1
    # (explicit instruction not to build speculative multi-provider
    # infrastructure ahead of a second provider actually existing).
    provider = Column(String, nullable=False, default="google")
    refresh_token = Column(String, nullable=False)
    access_token = Column(String, nullable=True)
    access_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    google_account_email = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
