"""Unit tests — FernetPostgresVault adapter (Task 3.3 RED → 3.4 GREEN).

Uses a mocked async session to avoid Postgres dependency.
Tests cover:
  - Fernet encrypt→decrypt round-trip
  - Corrupted ciphertext → VaultDecryptError
  - list_keys returns key names not values
  - store is idempotent (upsert semantics)
  - get of missing key → SecretNotFound
  - missing VAULT_MASTER_KEY → MasterKeyMissingError
  - audit log is written on every operation (3.8)
  - vault_audit_log has no UPDATE/DELETE methods on public API (3.8 tamper prevention)
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from core.tenants.base import TenantId
from core.vault.base import MasterKeyMissingError, SecretNotFound, VaultDecryptError
from core.vault.fernet_postgres import FernetPostgresVault


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MASTER_KEY = Fernet.generate_key().decode()


def _vault(caller_context: str | None = None) -> FernetPostgresVault:
    """Instantiate vault with a valid master key."""
    with patch.dict(os.environ, {"VAULT_MASTER_KEY": MASTER_KEY, "ENV": "test"}):
        return FernetPostgresVault(caller_context=caller_context)


def _tenant_id() -> TenantId:
    return TenantId(uuid4())


# ---------------------------------------------------------------------------
# Task 3.3 — Fail-fast guard
# ---------------------------------------------------------------------------


class TestMasterKeyGuard:
    def test_missing_master_key_raises_in_production(self) -> None:
        env = {"ENV": "production"}
        if "VAULT_MASTER_KEY" in os.environ:
            del os.environ["VAULT_MASTER_KEY"]
        with patch.dict(os.environ, env, clear=False):
            # Remove VAULT_MASTER_KEY from env to simulate missing key
            env_without_key = {k: v for k, v in os.environ.items() if k != "VAULT_MASTER_KEY"}
            with patch.dict(os.environ, env_without_key, clear=True):
                with pytest.raises((MasterKeyMissingError, RuntimeError)):
                    FernetPostgresVault()

    def test_invalid_fernet_key_raises(self) -> None:
        with patch.dict(os.environ, {"VAULT_MASTER_KEY": "not-a-valid-fernet-key", "ENV": "test"}):
            with pytest.raises((MasterKeyMissingError, ValueError, Exception)):
                FernetPostgresVault()

    def test_valid_key_instantiates_ok(self) -> None:
        vault = _vault()
        assert isinstance(vault, FernetPostgresVault)


# ---------------------------------------------------------------------------
# Task 3.3 — Fernet round-trip (encrypt → decrypt)
# ---------------------------------------------------------------------------


class TestFernetRoundTrip:
    def test_encrypt_decrypt_round_trip(self) -> None:
        """Directly test the _encrypt / _decrypt methods."""
        vault = _vault()
        plaintext = "my-super-secret-value"
        ciphertext = vault._encrypt(plaintext)
        assert isinstance(ciphertext, bytes)
        assert ciphertext != plaintext.encode()  # it's encrypted
        recovered = vault._decrypt(ciphertext)
        assert recovered == plaintext

    def test_different_calls_produce_different_ciphertexts(self) -> None:
        """Fernet uses a random IV — same plaintext encrypts differently each time."""
        vault = _vault()
        c1 = vault._encrypt("same-value")
        c2 = vault._encrypt("same-value")
        assert c1 != c2  # different due to random IV

    def test_corrupted_ciphertext_raises_decrypt_error(self) -> None:
        vault = _vault()
        bad_ciphertext = b"this-is-not-fernet-ciphertext"
        with pytest.raises(VaultDecryptError):
            vault._decrypt(bad_ciphertext)

    def test_truncated_ciphertext_raises_decrypt_error(self) -> None:
        vault = _vault()
        real = vault._encrypt("value")
        truncated = real[:10]
        with pytest.raises(VaultDecryptError):
            vault._decrypt(truncated)


# ---------------------------------------------------------------------------
# Task 3.3 — store / get / delete / list_keys with mocked session
# ---------------------------------------------------------------------------


def _make_mock_session(rows: list | None = None) -> AsyncMock:
    """Build an AsyncMock that mimics an async SQLAlchemy session."""
    session = AsyncMock()
    session.begin = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows or []
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


class TestStoreGetDeleteWithMock:
    @pytest.mark.asyncio
    async def test_get_missing_key_raises_secret_not_found(self) -> None:
        vault = _vault()
        tenant_id = _tenant_id()
        mock_session = _make_mock_session(rows=None)
        # scalar_one_or_none returns None → key doesn't exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(SecretNotFound):
            await vault.get(tenant_id, "missing_key", session=mock_session)

    @pytest.mark.asyncio
    async def test_list_keys_returns_names_not_values(self) -> None:
        vault = _vault()
        tenant_id = _tenant_id()

        # Simulate two TenantSecretORM rows with key_name only
        row1 = MagicMock()
        row1.key_name = "api_key"
        row2 = MagicMock()
        row2.key_name = "oauth_token"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [row1, row2]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_add_audit = AsyncMock()
        mock_session.add = mock_add_audit
        mock_session.flush = AsyncMock()

        keys = await vault.list_keys(tenant_id, session=mock_session)

        assert keys == ["api_key", "oauth_token"]
        # Values must not appear
        assert "value" not in keys
        assert "ciphertext" not in keys

    @pytest.mark.asyncio
    async def test_store_writes_audit_log(self) -> None:
        """store() must call session.add() at least once for the audit log."""
        vault = _vault()
        tenant_id = _tenant_id()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # new secret → insert

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        await vault.store(tenant_id, "api_key", "secret-value", session=mock_session)

        # session.add must be called at least twice: once for the secret, once for audit
        assert mock_session.add.call_count >= 2

    @pytest.mark.asyncio
    async def test_get_writes_audit_log(self) -> None:
        """get() must write an audit record even on success."""
        vault = _vault()
        tenant_id = _tenant_id()

        encrypted = vault._encrypt("secret-value")
        mock_secret_orm = MagicMock()
        mock_secret_orm.ciphertext = encrypted
        mock_secret_orm.tenant_id = tenant_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_secret_orm

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        result = await vault.get(tenant_id, "api_key", session=mock_session)

        assert result == "secret-value"
        # audit row must have been added
        assert mock_session.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_delete_missing_key_raises_secret_not_found(self) -> None:
        vault = _vault()
        tenant_id = _tenant_id()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        with pytest.raises(SecretNotFound):
            await vault.delete(tenant_id, "nonexistent_key", session=mock_session)

    @pytest.mark.asyncio
    async def test_delete_existing_key_writes_audit_log(self) -> None:
        vault = _vault()
        tenant_id = _tenant_id()

        mock_secret_orm = MagicMock()
        mock_secret_orm.tenant_id = tenant_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_secret_orm

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.delete = AsyncMock()
        mock_session.flush = AsyncMock()

        await vault.delete(tenant_id, "api_key", session=mock_session)

        # Must have deleted the ORM object and added an audit row
        mock_session.delete.assert_called_once_with(mock_secret_orm)
        assert mock_session.add.call_count >= 1


# ---------------------------------------------------------------------------
# Task 3.8 — Tamper prevention: no UPDATE/DELETE on audit log in public API
# ---------------------------------------------------------------------------


class TestAuditLogTamperPrevention:
    def test_no_update_audit_log_method(self) -> None:
        """FernetPostgresVault must NOT expose update_audit_log or similar."""
        public_methods = [m for m in dir(FernetPostgresVault) if not m.startswith("_")]
        audit_mutators = [m for m in public_methods if "audit" in m.lower() and
                         any(word in m.lower() for word in ("update", "delete", "remove", "clear", "purge"))]
        assert audit_mutators == [], f"Found audit mutators: {audit_mutators}"

    def test_no_delete_audit_log_method(self) -> None:
        """FernetPostgresVault must NOT expose delete_audit_log or similar."""
        public_methods = [m for m in dir(FernetPostgresVault) if not m.startswith("_")]
        forbidden = {"delete_audit_log", "remove_audit_log", "purge_audit_log",
                     "clear_audit_log", "update_audit_log"}
        overlap = set(public_methods) & forbidden
        assert overlap == set(), f"Forbidden audit methods found: {overlap}"

    @pytest.mark.asyncio
    async def test_store_twice_produces_two_audit_rows(self) -> None:
        """Calling store twice (upsert) must produce 2 audit rows, not 1.

        This verifies that audit rows are NEVER updated — each operation
        always produces a new INSERT into vault_audit_log.
        """
        vault = _vault()
        tenant_id = _tenant_id()
        add_calls = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock(side_effect=lambda obj: add_calls.append(type(obj).__name__))
        mock_session.flush = AsyncMock()

        await vault.store(tenant_id, "api_key", "value-1", session=mock_session)
        # second store — simulate existing key (upsert)
        existing_orm = MagicMock()
        existing_orm.tenant_id = tenant_id
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = existing_orm
        mock_session.execute = AsyncMock(return_value=mock_result2)

        await vault.store(tenant_id, "api_key", "value-2", session=mock_session)

        # Count audit log adds — class name will be VaultAuditLogORM
        audit_adds = [c for c in add_calls if "audit" in c.lower() or "log" in c.lower()
                      or "Audit" in c or "Log" in c]
        # At minimum 2 audit rows must have been added (one per store call)
        assert len(audit_adds) >= 2, f"Expected ≥2 audit rows, got: {add_calls}"
