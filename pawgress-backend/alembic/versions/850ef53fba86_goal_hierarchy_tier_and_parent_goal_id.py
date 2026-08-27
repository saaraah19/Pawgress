"""goal hierarchy: tier and parent_goal_id

Revision ID: 850ef53fba86
Revises: a6bf4696c8da
Create Date: 2026-08-15 18:59:48.816134

Hand-corrected after autogenerate — two real bugs in the raw output, fixed
here and verified by an actual upgrade/downgrade round-trip before this was
considered done (see docs/PROGRESS.md for the verification log):

1. Postgres ENUM types are NOT created automatically by
   `op.add_column(..., sa.Enum(...))` — autogenerate emits the ALTER TABLE
   but never a CREATE TYPE, so the raw generated migration fails outright
   on a real Postgres database ("type goaltier does not exist"). Fixed by
   explicitly creating the enum type before adding the column, and
   dropping it explicitly in downgrade (after the column that uses it is
   gone, not before).
2. The self-referential foreign key was created unnamed, which autogenerate
   then can't reference on downgrade (`op.drop_constraint(None, ...)` is
   not valid) — the raw generated downgrade would fail. Fixed by naming
   the constraint explicitly on create and referencing that same name on
   drop.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '850ef53fba86'
down_revision: Union[str, None] = 'a6bf4696c8da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

goal_tier_enum = postgresql.ENUM(
    "Annual", "Quarterly", "Project", "Milestone", name="goaltier"
)

FK_NAME = "fk_goals_parent_goal_id_goals"


def upgrade() -> None:
    bind = op.get_bind()
    goal_tier_enum.create(bind, checkfirst=True)

    op.add_column(
        "goals",
        sa.Column(
            "tier",
            postgresql.ENUM("Annual", "Quarterly", "Project", "Milestone", name="goaltier", create_type=False),
            nullable=True,
        ),
    )
    op.add_column("goals", sa.Column("parent_goal_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_goals_parent_goal_id"), "goals", ["parent_goal_id"], unique=False)
    op.create_foreign_key(FK_NAME, "goals", "goals", ["parent_goal_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint(FK_NAME, "goals", type_="foreignkey")
    op.drop_index(op.f("ix_goals_parent_goal_id"), table_name="goals")
    op.drop_column("goals", "parent_goal_id")
    op.drop_column("goals", "tier")

    bind = op.get_bind()
    goal_tier_enum.drop(bind, checkfirst=True)
