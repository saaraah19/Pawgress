"""add planner_entries (weekly/monthly planner)

Revision ID: e3f2a9c17d84
Revises: ac59b87b6730
Create Date: 2026-09-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e3f2a9c17d84'
down_revision: Union[str, None] = 'ac59b87b6730'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

planner_period_type_enum = postgresql.ENUM("Week", "Month", name="plannerperiodtype")


def upgrade() -> None:
    # Do NOT call planner_period_type_enum.create(...) separately — the
    # habits migration (3590ee8e620b) is the proven working pattern here:
    # embedding the ENUM object directly in create_table's column list is
    # what actually creates the Postgres type, and Alembic/SQLAlchemy
    # handles that internally. A prior draft of this migration ALSO called
    # .create(bind, checkfirst=True) before create_table — redundant, and
    # it broke on real Postgres with "type already exists" (SQLite never
    # caught this, since SQLite has no native enum type to conflict over —
    # this class of bug is only ever visible against a real Postgres run).
    op.create_table(
        "planner_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_type", planner_period_type_enum, nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("intention", sa.Text(), nullable=True),
        sa.Column("reflection", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "period_type", "period_start", name="uq_planner_entry_period"),
    )
    op.create_index(op.f("ix_planner_entries_user_id"), "planner_entries", ["user_id"], unique=False)
    op.create_index(op.f("ix_planner_entries_period_start"), "planner_entries", ["period_start"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_planner_entries_period_start"), table_name="planner_entries")
    op.drop_index(op.f("ix_planner_entries_user_id"), table_name="planner_entries")
    op.drop_table("planner_entries")

    # Same order as the habits migration's downgrade: drop the table
    # first, then the enum type — a type can't be dropped while a column
    # still references it.
    bind = op.get_bind()
    planner_period_type_enum.drop(bind, checkfirst=True)
