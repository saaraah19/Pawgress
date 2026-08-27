"""add habits and habit completions

Revision ID: 3590ee8e620b
Revises: 6889870f5bf3
Create Date: 2026-08-18 09:10:25.537003

Hand-corrected after autogenerate, same class of bug as the goal
hierarchy migration (850ef53fba86): CREATE TABLE with an inline
sa.Enum column does create the Postgres ENUM type correctly on
upgrade, but DROP TABLE does not automatically drop that type on
downgrade — verified directly (habitfrequency was left as an
orphaned type in \\dT after a raw downgrade, exactly like goaltier
was before). Fixed by explicitly dropping the enum type at the end
of downgrade(), after the table that uses it is already gone.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3590ee8e620b'
down_revision: Union[str, None] = '6889870f5bf3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

habit_frequency_enum = postgresql.ENUM("Daily", "WeeklyCount", name="habitfrequency")


def upgrade() -> None:
    op.create_table('habits',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('label', sa.String(), nullable=False),
    sa.Column('frequency', habit_frequency_enum, nullable=False),
    sa.Column('weekly_target', sa.Integer(), nullable=True),
    sa.Column('goal_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['goal_id'], ['goals.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_habits_goal_id'), 'habits', ['goal_id'], unique=False)
    op.create_index(op.f('ix_habits_user_id'), 'habits', ['user_id'], unique=False)
    op.create_table('habit_completions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('habit_id', sa.UUID(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['habit_id'], ['habits.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('habit_id', 'date', name='uq_habit_completion_day')
    )
    op.create_index(op.f('ix_habit_completions_habit_id'), 'habit_completions', ['habit_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_habit_completions_habit_id'), table_name='habit_completions')
    op.drop_table('habit_completions')
    op.drop_index(op.f('ix_habits_user_id'), table_name='habits')
    op.drop_index(op.f('ix_habits_goal_id'), table_name='habits')
    op.drop_table('habits')

    bind = op.get_bind()
    habit_frequency_enum.drop(bind, checkfirst=True)
