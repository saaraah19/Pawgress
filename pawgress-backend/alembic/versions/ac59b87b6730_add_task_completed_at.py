"""add task completed_at (Wistful mood tier)

Revision ID: ac59b87b6730
Revises: cb200d229e68
Create Date: 2026-09-13 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac59b87b6730'
down_revision: Union[str, None] = 'cb200d229e68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable, no server_default — existing rows simply have NULL, which
    # is the correct value for "not completed" / "completed before this
    # column existed and we have no real timestamp for it." The mood
    # calculator's has_completed_ever check only needs ONE non-null row to
    # exist going forward; it doesn't need historical completions
    # backfilled to behave correctly (see companion/mood_calculator.py).
    op.add_column('tasks', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('tasks', 'completed_at')
