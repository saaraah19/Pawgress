"""
calendar_integration/schemas.py — request/response shapes for the
Calendar module. None of these ever carry a raw token — that's enforced
here structurally (the fields simply don't exist on these models), not
just by convention in the route handlers.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CalendarStatusResponse(BaseModel):
    connected: bool
    accountEmail: Optional[str] = None


class CalendarOAuthStartResponse(BaseModel):
    authorizationUrl: str


class CalendarEventResponse(BaseModel):
    id: str
    title: str
    start: datetime
    end: datetime
    allDay: bool
    location: Optional[str] = None
