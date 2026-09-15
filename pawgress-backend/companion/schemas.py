"""
companion/schemas.py

Deliberately exposes mood only — no timestamp, no "last active" field, no
streak/history data. Domain Model §4.5 models CatCompanionState with a
"last updated timestamp" attribute, but that's an internal modeling detail
for a persisted entity; this implementation computes mood live and never
persists a timestamp to begin with (see mood_calculator.py's module
docstring), so there's nothing to expose — and deliberately nothing added
here to create one. Exposing any time-based field on this response is
exactly the kind of "small, obviously fine" addition the Handover warns
against (an absence-duration signal creeping in through a side door), so
this schema stays minimal on purpose, not by oversight.
"""

from typing import Literal
from pydantic import BaseModel


class CompanionStateResponse(BaseModel):
    # Wistful added 2026-09-13 — companion/mood_calculator.py's
    # CatMoodState enum was updated for the Wistful rebuild, but this
    # response schema's own Literal type was never updated to match, so
    # every response that computed Wistful raised a pydantic
    # ValidationError instead of ever reaching the client. Caught by a
    # real pytest run, not by py_compile (a Literal mismatch is a runtime
    # validation error, not a syntax error) and not by code review either
    # — I updated the enum and the frontend type but missed this one
    # schema in between, which is exactly the kind of single-file miss
    # that a real request/response round trip catches and static review
    # doesn't.
    mood: Literal["Neutral", "Attentive", "Content", "Wistful"]
