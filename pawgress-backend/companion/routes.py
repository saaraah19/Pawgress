"""
companion/routes.py

FR-6.1 — the cat's mood/state reaction to activity. Read-only: this module
has exactly one endpoint and it never mutates anything, consistent with
Domain Model §10.2 (CatMoodStateCalculator reads Task/Capture history, never
writes to it) and the Companion/Productivity-Core isolation in Domain Model
§3.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from shared.database import get_db
from identity.auth import get_current_user
from identity.models import User
from companion.mood_calculator import calculate_mood
from companion.schemas import CompanionStateResponse

router = APIRouter(prefix="/companion", tags=["companion"])


@router.get("/state", response_model=CompanionStateResponse)
def get_companion_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mood = calculate_mood(db, current_user.id)
    return CompanionStateResponse(mood=mood.value)
