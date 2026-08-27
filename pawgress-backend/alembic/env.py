"""
alembic/env.py

Wired to shared/config.py's settings and shared/database.py's Base, exactly
like every other module in this codebase — no hardcoded connection string
here, and no separate metadata definition that could drift from the real
models. `target_metadata = Base.metadata` after importing every model
module is what makes `alembic revision --autogenerate` see the full,
real schema (Identity + Productivity Core) rather than an empty one.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Make the backend package importable when Alembic is invoked from
# pawgress-backend/ (its working directory), same as init_db.py assumes.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.config import settings
from shared.database import Base

# Registers every model's table on Base.metadata — required even though the
# names aren't used directly below (same pattern as init_db.py).
import identity.models  # noqa: F401
import productivity.models  # noqa: F401
import journal.models  # noqa: F401
import habits.models  # noqa: F401
import calendar_integration.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Real connection string comes from the app's own settings (DATABASE_URL),
# not from alembic.ini — keeps exactly one source of truth for how to reach
# the database, whether that's local dev or Sarah's real Neon instance.
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
