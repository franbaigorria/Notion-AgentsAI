"""Shared fixtures for integration tests.

Requirements:
  - Postgres running on port 55432 (via docker compose up -d postgres) OR
    on port 5432 (Homebrew). Set DATABASE_URL env var to override.
  - VAULT_MASTER_KEY set to a valid Fernet key for vault integration tests.
    Generate one: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

If the DB is not reachable, all tests in this directory are SKIPPED with a
clear message — they are never expected to fail hard in environments without
Postgres (e.g. CI without a Postgres service, M1 dev machines with Docker off).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet

# Set ENV=test BEFORE any core.db import to bypass the fail-fast guard.
os.environ.setdefault("ENV", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://voiceagent:voiceagent@localhost:55432/voiceagent_test",
)
# Ensure VAULT_MASTER_KEY is available for vault fixtures
if not os.environ.get("VAULT_MASTER_KEY"):
    os.environ["VAULT_MASTER_KEY"] = Fernet.generate_key().decode()

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


# ---------------------------------------------------------------------------
# Postgres availability check
# ---------------------------------------------------------------------------


async def _postgres_is_available(url: str) -> bool:
    """Try to connect to Postgres. Returns False if connection fails."""
    try:
        engine = create_async_engine(url, poolclass=NullPool, connect_args={"timeout": 3})
        async with engine.connect():
            pass
        await engine.dispose()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Session-scoped engine — schema via Alembic
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def pg_engine() -> AsyncEngine:  # type: ignore[return]
    """Create async engine for the test session.

    Uses Alembic (upgrade head / downgrade base) to manage schema instead of
    Base.metadata.create_all, so integration tests exercise real migrations.
    Skips the entire session if Postgres is not reachable.
    """
    import asyncio

    from alembic import command
    from alembic.config import Config

    url = os.environ["DATABASE_URL"]
    available = await _postgres_is_available(url)
    if not available:
        pytest.skip(
            "Postgres not available on port 55432. "
            "Run 'docker compose up -d postgres' and retry."
        )

    engine = create_async_engine(url, poolclass=NullPool, echo=False)

    # Run Alembic migrations in a thread (alembic's command API is sync but
    # the env.py internally uses asyncio.run — so we use run_in_executor to avoid
    # blocking the event loop while Alembic takes over the event loop for its run)
    alembic_cfg = Config("alembic.ini")
    # Pass DATABASE_URL via env var — alembic/env.py reads it from os.environ
    os.environ["DATABASE_URL"] = url
    await asyncio.get_event_loop().run_in_executor(
        None, lambda: command.upgrade(alembic_cfg, "head")
    )

    yield engine

    # Tear down schema via Alembic downgrade to base after the full session
    await asyncio.get_event_loop().run_in_executor(
        None, lambda: command.downgrade(alembic_cfg, "base")
    )

    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def pg_session_factory(pg_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return a session factory bound to the test engine."""
    return async_sessionmaker(
        bind=pg_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# ---------------------------------------------------------------------------
# Function-scoped session — each test gets a clean slate via DELETE
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session(
    pg_engine: AsyncEngine,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncSession:  # type: ignore[return]
    """Yield a fresh session per test.

    Deletes all rows from all test tables after each test to guarantee isolation.
    """
    from core.db.models import Base

    async with pg_session_factory() as session:
        async with session.begin():
            yield session

    # Delete all rows after the test (outside the session context)
    async with pg_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


# ---------------------------------------------------------------------------
# Vault fixture — injects db_session as the session_factory
#
# The vault manages sessions internally via session_factory. In tests, we inject
# a factory that yields the SAME db_session so vault operations are visible to
# test assertions running in that session (no cross-transaction visibility issues).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def vault(db_session: AsyncSession) -> "FernetPostgresVault":  # noqa: F821
    """Return a FernetPostgresVault wired to the current test db_session.

    Injecting a session_factory that returns the existing db_session ensures
    that vault.store()/get()/delete() operations run in the same transaction
    as the test, making rows visible to subsequent db_session queries without
    committing.
    """
    from core.vault.fernet_postgres import FernetPostgresVault

    @asynccontextmanager
    async def _shared_session_factory():
        """Yield the existing db_session without opening a new transaction."""
        yield db_session

    return FernetPostgresVault(
        caller_context="integration_test",
        session_factory=_shared_session_factory,
    )
