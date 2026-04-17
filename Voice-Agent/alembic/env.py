"""Alembic async migration environment.

Uses the shared async engine from ``core.db.engine`` so migrations always run
against the same DATABASE_URL that the application uses at runtime.
``target_metadata`` is bound to ``core.db.models.Base.metadata`` to enable
autogenerate support (``alembic revision --autogenerate``).
"""

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context

# ---------------------------------------------------------------------------
# Alembic config
# ---------------------------------------------------------------------------

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import models so autogenerate can diff against the live schema
# ---------------------------------------------------------------------------

# Must import models here so that Base.metadata is populated.
# ENV=test guard is needed because engine.py raises RuntimeError when
# DATABASE_URL is absent outside test mode.
os.environ.setdefault("ENV", "production")

from core.db.models import Base  # noqa: E402 — must come after env setup

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# URL resolution — prefer DATABASE_URL env var; fall back to alembic.ini
# ---------------------------------------------------------------------------


def _get_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    # Fallback: value set in alembic.ini [alembic] sqlalchemy.url
    return config.get_main_option("sqlalchemy.url", "")


# ---------------------------------------------------------------------------
# Offline mode — generate SQL without a live connection
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script output)."""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — async engine, real connection
# ---------------------------------------------------------------------------


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # detect column type changes during autogenerate
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create a NullPool async engine for migrations and run them."""
    url = _get_url()
    connectable: AsyncEngine = create_async_engine(
        url,
        poolclass=pool.NullPool,  # no pool for migration runs — one-shot
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (real DB connection)."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
