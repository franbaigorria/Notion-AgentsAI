"""Integration tests — FernetPostgresVault against real Postgres (Task 3.6 RED → 3.7 GREEN).

Requires:
  - Postgres running and DATABASE_URL pointing to voiceagent_test
  - VAULT_MASTER_KEY set to a valid Fernet key (conftest auto-generates one)

Tests cover:
  - store → get → delete CRUD round-trip
  - Audit log row written on every operation (store, get, delete, list_keys)
  - Cross-tenant isolation: tenant B cannot read tenant A secrets
  - list_keys returns only key names (no values)
  - Missing key → SecretNotFound
  - Upsert: store twice for same key overwrites ciphertext
  - BYTEA handling: ciphertext round-trips correctly through asyncpg
  - Tamper prevention: double store produces two audit rows, not one
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from core.db.models import TenantORM, TenantSecretORM, VaultAuditLogORM
from core.tenants.base import TenantId
from core.vault.base import SecretNotFound
from core.vault.fernet_postgres import FernetPostgresVault


# ---------------------------------------------------------------------------
# Helpers — create tenant rows directly (bypass TenantRegistry to keep scope tight)
# ---------------------------------------------------------------------------


async def _create_tenant(session, name: str = "Test Tenant") -> TenantORM:
    """Insert a minimal tenant row and return the ORM object."""
    tenant = TenantORM(
        id=uuid4(),
        name=name,
        vertical="test",
        config={},
        status="active",
    )
    session.add(tenant)
    await session.flush()
    return tenant


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def tenant_a(db_session):
    return await _create_tenant(db_session, name=f"Tenant-A-{uuid4()}")


@pytest_asyncio.fixture
async def tenant_b(db_session):
    return await _create_tenant(db_session, name=f"Tenant-B-{uuid4()}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFernetVaultCRUD:
    @pytest.mark.asyncio
    async def test_store_and_get_round_trip(self, vault: FernetPostgresVault, db_session, tenant_a):
        """store then get returns the original plaintext."""
        tid = TenantId(tenant_a.id)
        await vault.store(tid, "api_key", "super-secret-value", session=db_session)

        result = await vault.get(tid, "api_key", session=db_session)

        assert result == "super-secret-value"

    @pytest.mark.asyncio
    async def test_store_encrypts_at_rest(self, vault: FernetPostgresVault, db_session, tenant_a):
        """Ciphertext in DB must differ from plaintext."""
        tid = TenantId(tenant_a.id)
        await vault.store(tid, "secret", "plaintext-value", session=db_session)

        row = (
            await db_session.execute(
                select(TenantSecretORM).where(
                    TenantSecretORM.tenant_id == tenant_a.id,
                    TenantSecretORM.key_name == "secret",
                )
            )
        ).scalar_one()

        assert row.ciphertext != b"plaintext-value"
        assert isinstance(row.ciphertext, bytes)

    @pytest.mark.asyncio
    async def test_delete_removes_row(self, vault: FernetPostgresVault, db_session, tenant_a):
        """delete() physically removes the row from tenant_secrets."""
        tid = TenantId(tenant_a.id)
        await vault.store(tid, "temp_key", "temp-value", session=db_session)
        await vault.delete(tid, "temp_key", session=db_session)

        with pytest.raises(SecretNotFound):
            await vault.get(tid, "temp_key", session=db_session)

    @pytest.mark.asyncio
    async def test_get_missing_key_raises_secret_not_found(
        self, vault: FernetPostgresVault, db_session, tenant_a
    ):
        tid = TenantId(tenant_a.id)
        with pytest.raises(SecretNotFound):
            await vault.get(tid, "nonexistent_key", session=db_session)

    @pytest.mark.asyncio
    async def test_delete_missing_key_raises_secret_not_found(
        self, vault: FernetPostgresVault, db_session, tenant_a
    ):
        tid = TenantId(tenant_a.id)
        with pytest.raises(SecretNotFound):
            await vault.delete(tid, "nonexistent_key", session=db_session)

    @pytest.mark.asyncio
    async def test_list_keys_returns_names_only(
        self, vault: FernetPostgresVault, db_session, tenant_a
    ):
        """list_keys returns only key names, never ciphertexts or plaintext."""
        tid = TenantId(tenant_a.id)
        await vault.store(tid, "key_alpha", "value_alpha", session=db_session)
        await vault.store(tid, "key_beta", "value_beta", session=db_session)

        keys = await vault.list_keys(tid, session=db_session)

        assert set(keys) == {"key_alpha", "key_beta"}
        # Verify no value leakage
        for k in keys:
            assert "value" not in k

    @pytest.mark.asyncio
    async def test_list_keys_empty_tenant(self, vault: FernetPostgresVault, db_session, tenant_a):
        """list_keys on a tenant with no secrets returns empty list."""
        tid = TenantId(tenant_a.id)
        keys = await vault.list_keys(tid, session=db_session)
        assert keys == []

    @pytest.mark.asyncio
    async def test_upsert_overwrites_existing_secret(
        self, vault: FernetPostgresVault, db_session, tenant_a
    ):
        """Calling store twice for the same key updates the secret (upsert)."""
        tid = TenantId(tenant_a.id)
        await vault.store(tid, "token", "old-value", session=db_session)
        await vault.store(tid, "token", "new-value", session=db_session)

        result = await vault.get(tid, "token", session=db_session)
        assert result == "new-value"

        # Confirm only ONE row exists (upsert, not duplicate insert)
        count = (
            await db_session.execute(
                select(func.count()).select_from(TenantSecretORM).where(
                    TenantSecretORM.tenant_id == tenant_a.id,
                    TenantSecretORM.key_name == "token",
                )
            )
        ).scalar()
        assert count == 1

    @pytest.mark.asyncio
    async def test_bytea_round_trip(self, vault: FernetPostgresVault, db_session, tenant_a):
        """Ciphertext stored as BYTEA round-trips correctly through asyncpg."""
        tid = TenantId(tenant_a.id)
        # Store a value with unicode characters to stress BYTEA encoding
        await vault.store(tid, "unicode_key", "héllo wörld — ñ", session=db_session)
        result = await vault.get(tid, "unicode_key", session=db_session)
        assert result == "héllo wörld — ñ"


@pytest.mark.integration
class TestCrossTenantIsolation:
    @pytest.mark.asyncio
    async def test_tenant_a_cannot_read_tenant_b_secret(
        self, vault: FernetPostgresVault, db_session, tenant_a, tenant_b
    ):
        """Cross-tenant isolation: reading B's key as A raises SecretNotFound."""
        tid_a = TenantId(tenant_a.id)
        tid_b = TenantId(tenant_b.id)

        await vault.store(tid_b, "api_key", "secret_B", session=db_session)

        with pytest.raises(SecretNotFound):
            # A requests B's key — must NOT return B's secret
            await vault.get(tid_a, "api_key", session=db_session)

    @pytest.mark.asyncio
    async def test_same_key_name_per_tenant_is_independent(
        self, vault: FernetPostgresVault, db_session, tenant_a, tenant_b
    ):
        """Two tenants can store the same key name with different values."""
        tid_a = TenantId(tenant_a.id)
        tid_b = TenantId(tenant_b.id)

        await vault.store(tid_a, "api_key", "secret_A", session=db_session)
        await vault.store(tid_b, "api_key", "secret_B", session=db_session)

        assert await vault.get(tid_a, "api_key", session=db_session) == "secret_A"
        assert await vault.get(tid_b, "api_key", session=db_session) == "secret_B"

    @pytest.mark.asyncio
    async def test_list_keys_is_tenant_scoped(
        self, vault: FernetPostgresVault, db_session, tenant_a, tenant_b
    ):
        """list_keys returns only keys for the requesting tenant."""
        tid_a = TenantId(tenant_a.id)
        tid_b = TenantId(tenant_b.id)

        await vault.store(tid_a, "key_only_for_a", "value_a", session=db_session)
        await vault.store(tid_b, "key_only_for_b", "value_b", session=db_session)

        keys_a = await vault.list_keys(tid_a, session=db_session)
        keys_b = await vault.list_keys(tid_b, session=db_session)

        assert "key_only_for_a" in keys_a
        assert "key_only_for_b" not in keys_a
        assert "key_only_for_b" in keys_b
        assert "key_only_for_a" not in keys_b


@pytest.mark.integration
class TestAuditLog:
    @pytest.mark.asyncio
    async def test_store_writes_audit_row(
        self, vault: FernetPostgresVault, db_session, tenant_a
    ):
        """store() writes exactly one audit row with action='store'."""
        tid = TenantId(tenant_a.id)
        await vault.store(tid, "key1", "val1", session=db_session)

        audit_rows = (
            await db_session.execute(
                select(VaultAuditLogORM).where(
                    VaultAuditLogORM.tenant_id == tenant_a.id,
                    VaultAuditLogORM.action == "store",
                )
            )
        ).scalars().all()

        assert len(audit_rows) == 1
        assert audit_rows[0].key_name == "key1"
        assert audit_rows[0].caller_context == "integration_test"

    @pytest.mark.asyncio
    async def test_get_writes_audit_row(
        self, vault: FernetPostgresVault, db_session, tenant_a
    ):
        """get() writes an audit row with action='get'."""
        tid = TenantId(tenant_a.id)
        await vault.store(tid, "key2", "val2", session=db_session)
        await vault.get(tid, "key2", session=db_session)

        audit_rows = (
            await db_session.execute(
                select(VaultAuditLogORM).where(
                    VaultAuditLogORM.tenant_id == tenant_a.id,
                    VaultAuditLogORM.action == "get",
                )
            )
        ).scalars().all()

        assert len(audit_rows) == 1

    @pytest.mark.asyncio
    async def test_delete_writes_audit_row(
        self, vault: FernetPostgresVault, db_session, tenant_a
    ):
        """delete() writes an audit row with action='delete'."""
        tid = TenantId(tenant_a.id)
        await vault.store(tid, "key3", "val3", session=db_session)
        await vault.delete(tid, "key3", session=db_session)

        audit_rows = (
            await db_session.execute(
                select(VaultAuditLogORM).where(
                    VaultAuditLogORM.tenant_id == tenant_a.id,
                    VaultAuditLogORM.action == "delete",
                )
            )
        ).scalars().all()

        assert len(audit_rows) == 1

    @pytest.mark.asyncio
    async def test_list_keys_writes_audit_row(
        self, vault: FernetPostgresVault, db_session, tenant_a
    ):
        """list_keys() writes an audit row with action='list_keys'."""
        tid = TenantId(tenant_a.id)
        await vault.list_keys(tid, session=db_session)

        audit_rows = (
            await db_session.execute(
                select(VaultAuditLogORM).where(
                    VaultAuditLogORM.tenant_id == tenant_a.id,
                    VaultAuditLogORM.action == "list_keys",
                )
            )
        ).scalars().all()

        assert len(audit_rows) == 1

    @pytest.mark.asyncio
    async def test_failed_get_still_writes_audit_row(
        self, vault: FernetPostgresVault, db_session, tenant_a
    ):
        """Even a failed get() (SecretNotFound) writes an audit row."""
        tid = TenantId(tenant_a.id)

        with pytest.raises(SecretNotFound):
            await vault.get(tid, "missing_key", session=db_session)

        audit_rows = (
            await db_session.execute(
                select(VaultAuditLogORM).where(
                    VaultAuditLogORM.tenant_id == tenant_a.id,
                    VaultAuditLogORM.action == "get",
                    VaultAuditLogORM.key_name == "missing_key",
                )
            )
        ).scalars().all()

        assert len(audit_rows) == 1

    @pytest.mark.asyncio
    async def test_store_twice_produces_two_audit_rows(
        self, vault: FernetPostgresVault, db_session, tenant_a
    ):
        """Upsert (double store) must produce 2 audit rows — never an update."""
        tid = TenantId(tenant_a.id)
        await vault.store(tid, "key", "value-1", session=db_session)
        await vault.store(tid, "key", "value-2", session=db_session)

        audit_rows = (
            await db_session.execute(
                select(VaultAuditLogORM).where(
                    VaultAuditLogORM.tenant_id == tenant_a.id,
                    VaultAuditLogORM.action == "store",
                    VaultAuditLogORM.key_name == "key",
                )
            )
        ).scalars().all()

        assert len(audit_rows) == 2, (
            f"Expected 2 audit rows (one per store call), got {len(audit_rows)}. "
            "audit_log must be append-only — never update existing rows."
        )

    @pytest.mark.asyncio
    async def test_audit_log_has_no_plaintext_or_ciphertext(
        self, vault: FernetPostgresVault, db_session, tenant_a
    ):
        """Audit rows must NOT contain plaintext values or ciphertext."""
        tid = TenantId(tenant_a.id)
        await vault.store(tid, "secret_key", "my-plaintext-value", session=db_session)

        audit_rows = (
            await db_session.execute(select(VaultAuditLogORM))
        ).scalars().all()

        for row in audit_rows:
            # key_name is fine — it's the label, not the secret
            assert row.key_name in (None, "", "secret_key")
            # There should be no column that leaks plaintext
            assert not hasattr(row, "value")
            assert not hasattr(row, "ciphertext")
            assert not hasattr(row, "plaintext")
