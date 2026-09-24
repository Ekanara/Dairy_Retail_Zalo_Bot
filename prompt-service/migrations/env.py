"""
Alembic async migration environment for prompt-service.

Uses SQLAlchemy async engine so migrations run with asyncpg (the same
driver used by the application) rather than a sync psycopg2 fallback.

Run migrations
--------------
    cd prompt-service
    alembic upgrade head

Generate a new revision
-----------------------
    alembic revision --autogenerate -m "describe change"
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Alembic config object (gives access to alembic.ini values) ────────────────
config = context.config

# ── Standard Python logging, read from alembic.ini ───────────────────────────
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import ORM metadata so autogenerate can detect schema changes ─────────────
# Import Base *after* all models have been imported so metadata is complete.
from app.core.config import settings  # noqa: E402
from app.db.database import Base  # noqa: E402
from app.db import models  # noqa: E402, F401  ← side-effect import to register tables

target_metadata = Base.metadata

# Inject the runtime DATABASE_URL so alembic.ini can leave it blank
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


# ── Offline mode (generate SQL without connecting) ────────────────────────────


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Emits SQL to stdout rather than executing against a live DB.
    Useful for generating migration scripts for DBAs to review.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (execute against live DB) ────────────────────────────────────


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations inside a sync-bridge."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # no pool needed for migration runs
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online (connected) migration execution."""
    asyncio.run(run_async_migrations())


# ── Dispatch ──────────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
