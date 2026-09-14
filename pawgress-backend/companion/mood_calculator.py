"""
companion/mood_calculator.py

Domain Model §10.2 CatMoodStateCalculator: "Derives the current CatMoodState
from recent activity signals (read from Task/Capture history, but never
writes to them). This is the one place 'recent activity' and 'cat
presentation' are allowed to touch, and it's structurally one-directional —
Companion reads from Productivity Core, never the reverse."

This module reads Task/Capture rows to compute a mood; it never writes to
either table, and nothing in productivity/ imports from here — enforcing
Domain Model §3's context isolation (Companion never derives Productivity
Core's structuring behavior, Productivity Core never depends on Companion
state) at the module-boundary level, not just by convention.

Deliberately NOT modeled as a persisted CatCompanionState table. Domain
Model §4.5 describes CatCompanionState as "current-value-only, not a
history log" specifically to prevent it from becoming a hidden scoring
system — this implementation goes one step further: since mood is fully,
cheaply derivable from Task/Capture data that's already persisted, adding a
table to *cache* that derived value would only introduce a write path and
a staleness/invalidation problem with no corresponding benefit. See
docs/adr/0002-companion-mood-computed-live.md for the full reasoning and
tradeoffs.
"""

import enum
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from productivity.models import Task, Capture


class CatMoodState(str, enum.Enum):
    """Domain Model §7 — placeholder set, exactly as illustrated there:
    'e.g., Neutral, Content, Attentive'. A small, closed enum by design —
    not open-ended, not numeric (Functional Requirements A5's resolution:
    the model must be a minimal current-value abstraction, not a hidden
    scoring system). The exact states, count, and trigger logic remain a
    UX-phase decision (A5 is still only partially resolved) — this is a
    reasonable, defensible first implementation, not treated as final.

    WISTFUL — added 2026-09, a deliberate, narrow, scoped EXCEPTION to
    this file's own governing rule below (see calculate_mood's docstring
    for why it doesn't violate FR-6.2's spirit despite being duration-
    based). Reuses existing calm/sleepy expression assets on the frontend
    (no new art), carries no unique copy anywhere in the product, and
    recovers silently and instantly on the next completion."""

    NEUTRAL = "Neutral"
    ATTENTIVE = "Attentive"
    CONTENT = "Content"
    WISTFUL = "Wistful"


# Provisional, explicitly tunable — Sarah may want to retune this after
# seeing it live (carried forward from the original design conversation).
# A single named constant here means that's a one-line change, not a hunt
# through the function body.
WISTFUL_THRESHOLD_DAYS = 3


def calculate_mood(db: Session, user_id) -> CatMoodState:
    """
    Invariant 6 / FR-6.2, the rule this function exists to make structurally
    true rather than merely policy: mood is never selected by an
    inactivity-only or negative-only signal. Concretely:

    - NEUTRAL is the zero-signal baseline for a brand-new user with no
      Task/Capture history at all yet — a fresh, calm starting point, not a
      "nothing's happened, that's sad" state (AC-6.2.1's spirit applied to
      day one, not just to returning after a gap).
    - ATTENTIVE and CONTENT are both selected by the *presence* of activity
      at different scopes (ever vs. today) — never by its absence. A user
      who was last active a month ago and a user who was last active a year
      ago land on exactly the same ATTENTIVE state; there is no continuum
      of "less and less present" the calculation could express even if it
      wanted to, because the calculation never measures how long it's been.

    Deliberately does NOT compute or compare against "time since last
    activity" as a duration — only two coarse, boolean signals (any activity
    ever; any activity today). This keeps the calculation incapable of
    expressing an absence-duration concept at all, consistent with the
    Handover's explicit warning against "any absence-duration display, even
    an internal-only 'last seen' badge" creeping in — here that's enforced
    by not computing a duration in the first place, not just by not
    displaying one.

    WISTFUL is the one deliberate, scoped exception to the paragraph above,
    approved directly (not something this file decided on its own). It IS a
    duration comparison — "has it been a few days since the last
    completion" — but differs from the inactivity-shaming pattern FR-6.2
    bans in every way that matters:
      - Scoped to completions specifically, not general inactivity — a user
        who's capturing and creating tasks but not finishing them is a
        different, narrower signal than "hasn't opened the app."
      - Requires having completed at least one task EVER first — a brand-
        new user is never shown as wistful; there's nothing to recover from
        on day one.
      - No new "sad" art — reuses the existing calm/sleepy expression
        weighting (companionConfig.ts), the same visual vocabulary already
        used for ordinary low-key moments, not a punishment-coded state.
      - No unique copy anywhere — the accessible name is keyed to
        expression (calm/sleepy), never to "wistful," so it's invisible in
        every text surface (screen readers included).
      - Recovers instantly and silently on the very next completion — no
        multi-day "cooldown," no gradual recovery arc. One completion, and
        it's simply CONTENT again, same as any other day with activity.
    This is a coarse boolean ("more than N days since last completion, yes
    or no") in the same spirit as ATTENTIVE/CONTENT's ever/today booleans —
    not a continuum, not a score, not something that gets "worse" the
    longer it's true.

    "Today" is a UTC calendar-day boundary — a simplification worth naming:
    it doesn't respect the user's local timezone, so a user just past
    midnight UTC could see ATTENTIVE despite having been active minutes ago
    in their own local "today." Acceptable for an MVP-minimal companion
    (FR-6.1's own framing — presentation and expression, not precision), and
    cheap to fix later without touching the state model itself.
    """
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    has_activity_ever = (
        db.query(Capture.id).filter(Capture.user_id == user_id).first() is not None
        or db.query(Task.id).filter(Task.user_id == user_id).first() is not None
    )
    if not has_activity_ever:
        return CatMoodState.NEUTRAL

    has_completed_ever = (
        db.query(Task.id).filter(Task.user_id == user_id, Task.completed_at.isnot(None)).first() is not None
    )
    if has_completed_ever:
        most_recent_completion = (
            db.query(func.max(Task.completed_at)).filter(Task.user_id == user_id).scalar()
        )
        wistful_cutoff = today_start - timedelta(days=WISTFUL_THRESHOLD_DAYS)
        if most_recent_completion is not None and most_recent_completion < wistful_cutoff:
            return CatMoodState.WISTFUL

    has_activity_today = (
        db.query(Capture.id)
        .filter(Capture.user_id == user_id, Capture.created_at >= today_start)
        .first()
        is not None
        or db.query(Task.id)
        .filter(Task.user_id == user_id, Task.created_at >= today_start)
        .first()
        is not None
    )

    return CatMoodState.CONTENT if has_activity_today else CatMoodState.ATTENTIVE
