"""Unit tests — DATABASE_URL scheme normalization (Phase 1.1 RED).

Context: Railway (and most managed Postgres providers) inject DATABASE_URL
with the driver-less scheme `postgresql://`. SQLAlchemy's async engine
requires the async driver suffix `postgresql+asyncpg://`. The engine module
normalizes the URL at init — these tests exercise that helper as a pure
function to keep it host-agnostic and trivially testable.
"""

from __future__ import annotations

import os

# Ensure the module-level guard in core.db.engine does not fail during import.
# When ENV == "test", a missing DATABASE_URL is permitted (tests mock the engine).
os.environ.setdefault("ENV", "test")

import pytest

from core.db.engine import _normalize_database_url


class TestNormalizeDatabaseUrl:
    """Phase 1.1 — validate scheme normalization for supported + unsupported URLs."""

    def test_rewrites_raw_postgresql_to_asyncpg(self) -> None:
        url = "postgresql://user:pw@host:5432/db"
        assert (
            _normalize_database_url(url) == "postgresql+asyncpg://user:pw@host:5432/db"
        )

    def test_passthrough_already_normalized_asyncpg(self) -> None:
        url = "postgresql+asyncpg://user:pw@host:5432/db"
        assert _normalize_database_url(url) == url

    def test_rewrites_psycopg_to_asyncpg(self) -> None:
        url = "postgresql+psycopg://user:pw@host:5432/db"
        assert (
            _normalize_database_url(url) == "postgresql+asyncpg://user:pw@host:5432/db"
        )

    def test_rejects_non_postgres_scheme(self) -> None:
        with pytest.raises(ValueError, match="Unsupported database scheme"):
            _normalize_database_url("mysql://user@host/db")

    def test_rejects_empty_url(self) -> None:
        with pytest.raises(ValueError, match="DATABASE_URL must not be empty"):
            _normalize_database_url("")

    def test_preserves_query_string(self) -> None:
        url = "postgresql://user:pw@host/db?sslmode=require"
        assert (
            _normalize_database_url(url)
            == "postgresql+asyncpg://user:pw@host/db?sslmode=require"
        )

    def test_preserves_raw_password_special_chars(self) -> None:
        url = "postgresql://user:p%40ss@host/db"
        assert (
            _normalize_database_url(url)
            == "postgresql+asyncpg://user:p%40ss@host/db"
        )
