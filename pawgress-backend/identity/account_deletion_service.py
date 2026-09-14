"""
identity/account_deletion_service.py

System Architecture §18: "because every aggregate is independently
identifiable by owning-User-ID, a full account deletion request is
architecturally a bounded, enumerable operation: delete all rows across
all tables where user_id matches, in dependency order." This is the
first real implementation of that promise — Functional Requirements
NFR-3/BR-10 established the architectural *requirement* (deletion must be
technically achievable) but explicitly deferred *shipping* it; this is
that shipping.

**The authoritative table registry.** System Architecture §18 names this
exact risk: "a single, authoritative internal registry of every table
that can contain user data... is a small process discipline, not a
technical system, but it's the actual mechanism that keeps BR-10 true as
the schema grows past what one person can hold in their head." This
module IS that registry — when a new table with a user_id (directly or
via a parent it belongs to) is added anywhere in the codebase, it must be
added to `delete_account`'s deletion sequence below, or BR-10 silently
stops being true for that table. There is no automated check for this
yet (a real gap — see this module's own docstring note below).

Deletion order matters even though only one FK in this schema currently
has DB-level ON DELETE CASCADE (habit_completions -> habits) — everything
else relies on NO ACTION/RESTRICT by default, so children must be deleted
before parents to avoid a foreign-key violation on Postgres. Order:
  1. field_correction_records (references tasks.id)
  2. habit_completions (references habits.id — DB-cascades already, but
     deleted explicitly too since SQLite in tests doesn't enforce FK
     constraints, and explicit is safer than relying on a DB behavior
     that differs between environments)
  3. tasks (references users.id, goals.id, captures.id) — must precede
     goals, since Task.goal_id references Goal
  4. habits (references users.id, goals.id) — must ALSO precede goals,
     for the same reason (Habit.goal_id references Goal) — this ordering
     bug (habits deleted after goals) existed in an earlier draft of this
     function and would have thrown a live FK violation on Postgres the
     first time a user with a goal-linked habit tried to delete their
     account, despite passing on SQLite tests (SQLite doesn't enforce FK
     constraints by default) — worth remembering as a reason to eventually
     test this against real Postgres, not just SQLite.
  5. captures (references users.id)
  6. goals (self-referencing parent_goal_id; references users.id)
  7. journal_entries (references users.id)
  8. calendar_connections (references users.id)
  9. the User row itself

All in one transaction — either everything for this user disappears, or
(on any error) nothing does. No soft-delete, no "deactivated" flag: this
is a real user-initiated deletion of their own data (Business Model §4's
distinction — this is not the business deleting data as a monetization
lever, which is banned; this is the user's own standing right over their
own data, same category as FR-3.5's task deletion).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from identity.models import User
from productivity.models import Task, Goal, Capture, FieldCorrectionRecord
from habits.models import Habit, HabitCompletion
from journal.models import JournalEntry
from calendar_integration.models import CalendarConnection


def delete_account(db: Session, user_id) -> None:
    task_ids = select(Task.id).where(Task.user_id == user_id)
    habit_ids = select(Habit.id).where(Habit.user_id == user_id)

    db.query(FieldCorrectionRecord).filter(FieldCorrectionRecord.task_id.in_(task_ids)).delete(
        synchronize_session=False
    )
    db.query(HabitCompletion).filter(HabitCompletion.habit_id.in_(habit_ids)).delete(synchronize_session=False)
    db.query(Task).filter(Task.user_id == user_id).delete(synchronize_session=False)
    db.query(Habit).filter(Habit.user_id == user_id).delete(synchronize_session=False)
    db.query(Capture).filter(Capture.user_id == user_id).delete(synchronize_session=False)
    db.query(Goal).filter(Goal.user_id == user_id).delete(synchronize_session=False)
    db.query(JournalEntry).filter(JournalEntry.user_id == user_id).delete(synchronize_session=False)
    db.query(CalendarConnection).filter(CalendarConnection.user_id == user_id).delete(synchronize_session=False)
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)

    db.commit()


# NOTE for whoever adds the next user-owned table: there is currently no
# automated test that fails if a new table is added here without being
# added to delete_account above (e.g. a future Memory table, per System
# Architecture §13). tests/test_account_deletion.py's
# test_every_user_owned_table_is_covered_by_deletion asserts against a
# hardcoded list of table names for exactly this reason — if you add a
# table, that test will need updating too, and its failure is the signal
# that this module needs updating.
