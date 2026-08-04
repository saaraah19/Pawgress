"""
productivity/goal_service.py

Domain Model §10.5 GoalDeletionService: "Invoked when a user deletes a Goal.
Finds every Task referencing that Goal and sets each Task's Goal reference to
null in the same operation, then removes the Goal itself." Direct enforcement
of Invariant 9 (§9) — unlink, never cascade-delete.

Deliberately a standalone function rather than logic embedded in the route or
in Task/Goal themselves: it coordinates across two aggregates, and Modeling
Principle 1 (small aggregates) means Goal shouldn't reach into Task directly
from within the model layer.
"""

from sqlalchemy.orm import Session

from productivity.models import Task, Goal


def delete_goal_and_unlink_tasks(db: Session, goal: Goal) -> None:
    """Unlink every Task referencing this Goal, then delete the Goal, as a
    single unit of work. Both statements are committed together — if either
    fails, neither is applied, so a Task can never be left silently orphaned
    from a Goal that no longer exists."""
    db.query(Task).filter(Task.goal_id == goal.id).update({Task.goal_id: None})
    db.delete(goal)
    db.commit()
