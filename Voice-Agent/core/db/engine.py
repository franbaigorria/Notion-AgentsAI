"""Async SQLAlchemy engine and session factory.

Reads DATABASE_URL from the environment at module import time.
Raises RuntimeError immediately if the variable is absent and ENV != "test",
so misconfiguration surfaces at startup — not at the first DB call.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ---------------------------------------------------------------------------
# Fail-fast env var guard
# ---------------------------------------------------------------------------

_ENV = os.getenv("ENV", "production")
_DATABASE_URL = os.getenv("DATABASE_URL")

if _DATABASE_URL is None and _ENV != "test":
    raise RuntimeError(
        "DATABASE_URL environment variable is required but not set. "
        "Set it to a postgresql+asyncpg:// connection string. "
        "Example: postgresql+asyncpg://user:pass@localhost:5432/voiceagent"
    )

# ---------------------------------------------------------------------------
# Engine factory (singleton pattern — call get_engine() everywhere)
# ---------------------------------------------------------------------------

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Return the shared async engine, creating it on first call.

    Pool settings are conservative defaults suitable for Railway / single-dyno
    deployments. Adjust via env vars if needed.
    """
    global _engine
    if _engine is None:
        if _DATABASE_URL is None:
            raise RuntimeError(
                "DATABASE_URL is not set. Cannot create engine in test mode without a URL."
            )
        _engine = create_async_engine(
            _DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_timeout=3,  # seconds — fail fast on pool exhaustion
            pool_pre_ping=True,  # detect stale connections before checkout
            echo=os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
        )
    return _engine


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the shared session factory, creating it on first call."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that yields a transactional session.

    Usage::

        async with get_session() as session:
            result = await session.execute(select(TenantORM))
    """
    factory = get_session_factory()
    async with factory() as session:
        async with session.begin():
            yield session


# ---------------------------------------------------------------------------
# Shutdown hook — call on SIGTERM / SIGINT to drain the connection pool
# ---------------------------------------------------------------------------

async def dispose_engine() -> None:
    """Gracefully drain the connection pool.

    Wire this to your process shutdown handler::

        import asyncio, signal
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(dispose_engine()))
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
