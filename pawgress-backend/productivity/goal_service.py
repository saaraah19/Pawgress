"""
productivity/goal_service.py

Domain Model §10.5 GoalDeletionService, extended for V2 hierarchy (Blueprint
§13). Two responsibilities live here, both because they coordinate across
what would otherwise be separate concerns (Modeling Principle 1 — small
aggregates — means this logic doesn't belong embedded in the Goal model
itself):

1. Deleting a Goal never cascades to anything it references or is
   referenced by — Tasks AND child Goals are both unlinked, never deleted,
   in the same transaction as removing the Goal. Direct extension of
   Domain Model Invariant 9 to the new parent/child relationship: the
   same "unlink, don't cascade" principle that already governed Task
   ownership now governs Goal ownership of other Goals too.
2. A parent/child link between two Goals is only valid if it can't create
   an inconsistent or cyclic structure — validated here, once, so the
   rule can't be silently bypassed from a code path that isn't this
   function (same reasoning as ADR 0001's decision to keep the Task
   unlink in application code rather than DB-level cascade).
"""

from sqlalchemy.orm import Session

from productivity.models import Task, Goal, GoalTier, GOAL_TIER_RANK


class InvalidGoalParentError(Exception):
    """Raised when a proposed parent_goal_id would violate the hierarchy
    invariant. Carries a plain-language reason the API layer can surface
    directly — no separate error-code translation needed."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def delete_goal_and_unlink_references(db: Session, goal: Goal) -> None:
    """Unlink every Task and every child Goal referencing this Goal, then
    delete the Goal itself, as a single unit of work. A child Goal is
    unlinked (parent_goal_id set to null), never deleted or re-parented to
    its former grandparent — re-parenting would be a real structural
    decision a user should make deliberately, not one this deletion should
    make silently on their behalf."""
    db.query(Task).filter(Task.goal_id == goal.id).update({Task.goal_id: None})
    db.query(Goal).filter(Goal.parent_goal_id == goal.id).update({Goal.parent_goal_id: None})
    db.delete(goal)
    db.commit()


def validate_parent_link(goal: Goal, parent: Goal | None) -> None:
    """Raises InvalidGoalParentError if `parent` is not a legal parent for
    `goal`. Called before persisting any change to Goal.parent_goal_id —
    both on initial link and on re-parenting.

    Rules, all direct consequences of the "hierarchy is earned, not
    assumed" principle (Domain Model §4.3) plus the ordering that makes
    cycles structurally impossible:
      - parent=None is always valid (clearing the link, or a goal that
        simply doesn't participate in hierarchy).
      - A goal cannot be its own parent.
      - Both the goal and the proposed parent must already have a tier
        set — an untiered goal can neither have a parent nor be one,
        since there's no rank to compare.
      - The parent's tier must be strictly higher (broader) than the
        goal's own tier. Because rank only ever strictly decreases moving
        down a chain, a cycle can never form — this single rule is the
        entire cycle-prevention mechanism, no separate ancestor-walk
        needed.
    """
    if parent is None:
        return
    if parent.id == goal.id:
        raise InvalidGoalParentError("A goal cannot be its own parent.")
    if goal.tier is None:
        raise InvalidGoalParentError("Assign this goal a tier before giving it a parent.")
    if parent.tier is None:
        raise InvalidGoalParentError("The chosen parent goal doesn't have a tier assigned yet.")
    if GOAL_TIER_RANK[GoalTier(parent.tier)] >= GOAL_TIER_RANK[GoalTier(goal.tier)]:
        raise InvalidGoalParentError(
            f"A {parent.tier} goal can't be the parent of a {goal.tier} goal — "
            f"the parent must be a broader tier."
        )
