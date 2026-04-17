"""Async SQLAlchemy engine and session factory.

Reads DATABASE_URL from the environment at module import time.
Raises RuntimeError immediately if the variable is absent and ENV != "test",
so misconfiguration surfaces at startup — not at the first DB call.

Accepts driver-less `postgresql://` URLs (as injected by Railway, Heroku, and
most managed Postgres providers) and auto-rewrites to `postgresql+asyncpg://`
at engine construction time. Also accepts `postgresql+psycopg://` for local
dev setups that prefer the sync driver string.
"""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

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
# URL scheme normalization
# ---------------------------------------------------------------------------

_ASYNCPG_PREFIX = "postgresql+asyncpg://"
_RAW_PREFIX = "postgresql://"
_PSYCOPG_PREFIX = "postgresql+psycopg://"

_url_rewrite_warned = False


def _normalize_database_url(url: str) -> str:
    """Normalize a Postgres URL to the `postgresql+asyncpg://` driver form.

    Accepts `postgresql://` (driver-less — as injected by Railway / Heroku /
    most managed Postgres providers), `postgresql+psycopg://` (sync driver),
    and `postgresql+asyncpg://` (already normalized). Raises ``ValueError``
    for unsupported schemes or empty input — callers get a descriptive
    failure at startup instead of a cryptic driver error mid-request.
    """
    if not url:
        raise ValueError("DATABASE_URL must not be empty")
    if url.startswith(_ASYNCPG_PREFIX):
        return url
    if url.startswith(_PSYCOPG_PREFIX):
        return _ASYNCPG_PREFIX + url[len(_PSYCOPG_PREFIX) :]
    if url.startswith(_RAW_PREFIX):
        return _ASYNCPG_PREFIX + url[len(_RAW_PREFIX) :]
    scheme = url.split("://", 1)[0] if "://" in url else url
    raise ValueError(
        f"Unsupported database scheme in DATABASE_URL: {scheme!r}. "
        "Accepted: postgresql://, postgresql+asyncpg://, postgresql+psycopg://."
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
    global _engine, _url_rewrite_warned
    if _engine is None:
        if _DATABASE_URL is None:
            raise RuntimeError(
                "DATABASE_URL is not set. Cannot create engine in test mode without a URL."
            )
        normalized = _normalize_database_url(_DATABASE_URL)
        if normalized != _DATABASE_URL and not _url_rewrite_warned:
            logger.warning(
                "DATABASE_URL scheme rewritten to postgresql+asyncpg:// for async driver. "
                "Source scheme: %s",
                _DATABASE_URL.split("://", 1)[0],
            )
            _url_rewrite_warned = True
        _engine = create_async_engine(
            normalized,
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
