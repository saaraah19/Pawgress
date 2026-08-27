"""
journal/routes.py

Plain CRUD, deliberately. No AI/Extraction call anywhere in this module —
per Domain Model §13, journaling and task-extraction are different intents,
and this module structurally cannot conflate them (it has no import of
ai_extraction at all). Every route is scoped to the authenticated user's
ID as a non-optional filter, same authorization pattern as every other
module (System Architecture §9).
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from shared.database import get_db
from identity.auth import get_current_user
from identity.models import User
from journal.models import JournalEntry
from journal.schemas import JournalEntryCreateRequest, JournalEntryUpdateRequest, JournalEntryResponse

router = APIRouter(prefix="/journal", tags=["journal"])


@router.post("", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
def create_journal_entry(
    payload: JournalEntryCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = JournalEntry(id=uuid.uuid4(), user_id=current_user.id, text=payload.text)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return JournalEntryResponse.from_model(entry)


@router.get("", response_model=list[JournalEntryResponse])
def list_journal_entries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == current_user.id)
        .order_by(JournalEntry.created_at.desc())
        .all()
    )
    return [JournalEntryResponse.from_model(e) for e in entries]


@router.patch("/{entry_id}", response_model=JournalEntryResponse)
def update_journal_entry(
    entry_id: uuid.UUID,
    payload: JournalEntryUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = (
        db.query(JournalEntry)
        .filter(JournalEntry.id == entry_id, JournalEntry.user_id == current_user.id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found.")
    entry.text = payload.text
    db.commit()
    db.refresh(entry)
    return JournalEntryResponse.from_model(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journal_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanent delete, no confirmation required beyond the single
    deliberate action — same reasoning as AC-3.5.1 for Task deletion."""
    entry = (
        db.query(JournalEntry)
        .filter(JournalEntry.id == entry_id, JournalEntry.user_id == current_user.id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found.")
    db.delete(entry)
    db.commit()
