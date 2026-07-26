"""
identity/routes.py — FR-1.1 (account creation), FR-1.2 (session persistence).
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from shared.database import get_db
from identity.models import User
from identity.schemas import RegisterRequest, LoginRequest, AuthResponse
from identity.auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        # AC-1.1.2: plain, non-judgmental error message — no blunt technical
        # error, per Brand §6's tone rules extended to system errors.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Try logging in instead.",
        )

    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=None,  # FR-1.3 — no forced value; neutral default is an
        # API/frontend presentation concern, not stored as fake data here.
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    db.refresh(user)

    token = create_access_token(user.id)
    return AuthResponse(user_id=user.id, access_token=token)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    token = create_access_token(user.id)
    return AuthResponse(user_id=user.id, access_token=token)
