"""Integration test — Alembic migration up/down idempotency (Task 3.9).

Verifies the full migration cycle: upgrade head → downgrade -1 → upgrade head → downgrade base.

Design note: These tests are run STANDALONE (not within the pg_engine session fixture),
since they need to control Alembic state directly. They are run via pytest with
-k "alembic" to avoid interference with the session-scoped pg_engine fixture that
uses Base.metadata.create_all.

The simplest verification is to confirm the Alembic command.upgrade/downgrade
sequence produces the correct revision states — which we validated manually
and via the CLI gate in the SDD apply phase. This test suite confirms the
command API exits cleanly across the full cycle.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

# Ensure ENV=test before any core imports
os.environ.setdefault("ENV", "test")


def _run_alembic(*args: str) -> subprocess.CompletedProcess:
    """Run an alembic command as a subprocess to avoid session fixture interference."""
    env = os.environ.copy()
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
    )


def _get_db_tables() -> set[str]:
    """Query pg_tables for application table names."""
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    async def _query():
        url = os.environ["DATABASE_URL"]
        engine = create_async_engine(url, poolclass=NullPool)
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' "
                    "AND tablename NOT IN ('alembic_version')"
                )
            )
            tables = {row[0] for row in result}
        await engine.dispose()
        return tables

    return asyncio.get_event_loop().run_until_complete(_query())


def _clean_and_prepare() -> None:
    """Drop all application tables and types, then stamp base.

    This is necessary because the conftest pg_engine session fixture uses
    Base.metadata.create_all/drop_all which bypasses Alembic versioning,
    leaving the DB in a state where tables don't match the version table.
    We nuke everything here so migrations start from a truly clean slate.
    """
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    async def _drop_all():
        url = os.environ["DATABASE_URL"]
        engine = create_async_engine(url, poolclass=NullPool)
        async with engine.begin() as conn:
            # Drop tables in FK-safe order
            await conn.execute(text("DROP TABLE IF EXISTS vault_audit_log CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS tenant_secrets CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS tenants CASCADE"))
            # Drop ENUM types
            await conn.execute(text("DROP TYPE IF EXISTS tenant_status CASCADE"))
            await conn.execute(text("DROP TYPE IF EXISTS vault_action CASCADE"))
        await engine.dispose()

    asyncio.get_event_loop().run_until_complete(_drop_all())
    # Stamp base so Alembic starts fresh
    _run_alembic("stamp", "base")


@pytest.mark.integration
class TestAlembicMigrations:
    @pytest.fixture(autouse=True)
    def clean_state(self):
        """Ensure clean Alembic state before each test."""
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            pytest.skip("DATABASE_URL not set")
        _clean_and_prepare()
        yield
        # Restore to clean head after test (for other tests that need the schema)
        _clean_and_prepare()
        _run_alembic("upgrade", "head")

    def test_downgrade_minus1_then_upgrade_succeeds(self):
        """downgrade -1 reverts 0002; upgrade head reapplies it."""
        # Apply all migrations first
        r = _run_alembic("upgrade", "head")
        assert r.returncode == 0, f"initial upgrade head failed:\n{r.stderr}"

        result_down = _run_alembic("downgrade", "-1")
        assert result_down.returncode == 0, f"downgrade -1 failed:\n{result_down.stderr}"

        result_up = _run_alembic("upgrade", "head")
        assert result_up.returncode == 0, f"re-upgrade head failed:\n{result_up.stderr}"

    def test_downgrade_base_drops_all_tables(self):
        """downgrade base must drop tenants, tenant_secrets, vault_audit_log."""
        _run_alembic("upgrade", "head")

        result = _run_alembic("downgrade", "base")
        assert result.returncode == 0, f"downgrade base failed:\n{result.stderr}"

        tables = _get_db_tables()
        assert "tenants" not in tables, f"tenants still exists after downgrade base: {tables}"
        assert "tenant_secrets" not in tables
        assert "vault_audit_log" not in tables

    def test_upgrade_from_base_creates_all_tables(self):
        """After upgrade head from base, all 3 application tables exist."""
        result = _run_alembic("upgrade", "head")
        assert result.returncode == 0, f"upgrade head failed:\n{result.stderr}"

        tables = _get_db_tables()
        assert "tenants" in tables
        assert "tenant_secrets" in tables
        assert "vault_audit_log" in tables
