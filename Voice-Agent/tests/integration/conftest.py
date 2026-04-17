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

from core.db.models import Base


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
# Session-scoped engine + schema creation
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def pg_engine() -> AsyncEngine:  # type: ignore[return]
    """Create async engine for the test session.

    Skips the entire session if Postgres is not reachable.
    """
    url = os.environ["DATABASE_URL"]
    available = await _postgres_is_available(url)
    if not available:
        pytest.skip(
            "Postgres not available on port 55432. "
            "Run 'docker compose up -d postgres' and retry."
        )

    engine = create_async_engine(url, poolclass=NullPool, echo=False)

    # Create all tables (idempotent — uses CREATE TABLE IF NOT EXISTS via checkfirst)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Tear down schema after the full session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

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
# Function-scoped session — each test gets a clean slate via TRUNCATE
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session(
    pg_engine: AsyncEngine,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncSession:  # type: ignore[return]
    """Yield a fresh session per test.

    Truncates all test tables after each test to guarantee isolation.
    Uses TRUNCATE ... CASCADE so FK-linked tables are cleaned in one shot.
    """
    async with pg_session_factory() as session:
        async with session.begin():
            yield session
        # Rollback is automatic on exit if not committed — but for TRUNCATE-based
        # cleanup we do an explicit truncate after each test.

    # Truncate all tables after the test (outside the session context)
    async with pg_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


# ---------------------------------------------------------------------------
# Vault fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def vault() -> "FernetPostgresVault":  # noqa: F821
    """Return a FernetPostgresVault instance for integration tests."""
    from core.vault.fernet_postgres import FernetPostgresVault

    return FernetPostgresVault(caller_context="integration_test")
