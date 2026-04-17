"""Unit tests — CredentialVault ABC contract (Task 3.1 RED).

Asserts the ABC, exception types, and VaultAccessLog dataclass exist
with the correct structure. Expected to fail with ImportError until
core/vault/base.py is created (Task 3.2 GREEN).
"""

from __future__ import annotations

import inspect
from abc import ABC
from dataclasses import fields as dc_fields
from datetime import datetime

import pytest


# ---------------------------------------------------------------------------
# Import — will raise ImportError until 3.2 is done
# ---------------------------------------------------------------------------

from core.vault.base import (
    CredentialVault,
    CrossTenantAccessError,
    MasterKeyMissingError,
    SecretNotFound,
    VaultAccessLog,
    VaultDecryptError,
)
from core.tenants.base import TenantId


# ---------------------------------------------------------------------------
# CredentialVault ABC
# ---------------------------------------------------------------------------


class TestCredentialVaultABC:
    def test_credential_vault_is_abstract(self) -> None:
        """CredentialVault must be an ABC — cannot be instantiated directly."""
        assert issubclass(CredentialVault, ABC)

    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            CredentialVault()  # type: ignore[abstract]

    def test_store_is_abstract(self) -> None:
        assert "store" in CredentialVault.__abstractmethods__

    def test_get_is_abstract(self) -> None:
        assert "get" in CredentialVault.__abstractmethods__

    def test_delete_is_abstract(self) -> None:
        assert "delete" in CredentialVault.__abstractmethods__

    def test_list_keys_is_abstract(self) -> None:
        assert "list_keys" in CredentialVault.__abstractmethods__

    def test_store_signature(self) -> None:
        sig = inspect.signature(CredentialVault.store)
        params = list(sig.parameters.keys())
        assert "tenant_id" in params
        assert "key_name" in params
        assert "value" in params

    def test_get_signature(self) -> None:
        sig = inspect.signature(CredentialVault.get)
        params = list(sig.parameters.keys())
        assert "tenant_id" in params
        assert "key_name" in params

    def test_delete_signature(self) -> None:
        sig = inspect.signature(CredentialVault.delete)
        params = list(sig.parameters.keys())
        assert "tenant_id" in params
        assert "key_name" in params

    def test_list_keys_signature(self) -> None:
        sig = inspect.signature(CredentialVault.list_keys)
        params = list(sig.parameters.keys())
        assert "tenant_id" in params


# ---------------------------------------------------------------------------
# Exception types
# ---------------------------------------------------------------------------


class TestVaultExceptions:
    def test_secret_not_found_is_exception(self) -> None:
        assert issubclass(SecretNotFound, Exception)

    def test_vault_decrypt_error_is_exception(self) -> None:
        assert issubclass(VaultDecryptError, Exception)

    def test_cross_tenant_access_error_is_exception(self) -> None:
        assert issubclass(CrossTenantAccessError, Exception)

    def test_master_key_missing_error_is_exception(self) -> None:
        assert issubclass(MasterKeyMissingError, Exception)

    def test_secret_not_found_can_be_raised(self) -> None:
        with pytest.raises(SecretNotFound):
            raise SecretNotFound("key not found")

    def test_vault_decrypt_error_can_be_raised(self) -> None:
        with pytest.raises(VaultDecryptError):
            raise VaultDecryptError("invalid ciphertext")

    def test_cross_tenant_access_error_can_be_raised(self) -> None:
        with pytest.raises(CrossTenantAccessError):
            raise CrossTenantAccessError("cross-tenant attempt")

    def test_master_key_missing_error_can_be_raised(self) -> None:
        with pytest.raises(MasterKeyMissingError):
            raise MasterKeyMissingError("VAULT_MASTER_KEY not set")


# ---------------------------------------------------------------------------
# VaultAccessLog dataclass
# ---------------------------------------------------------------------------


class TestVaultAccessLog:
    def test_vault_access_log_is_dataclass(self) -> None:
        field_names = {f.name for f in dc_fields(VaultAccessLog)}
        assert "tenant_id" in field_names
        assert "key_name" in field_names
        assert "action" in field_names
        assert "timestamp" in field_names

    def test_caller_context_is_optional(self) -> None:
        field_names = {f.name for f in dc_fields(VaultAccessLog)}
        assert "caller_context" in field_names

    def test_vault_access_log_instantiation(self) -> None:
        from uuid import uuid4

        log = VaultAccessLog(
            tenant_id=TenantId(uuid4()),
            key_name="api_key",
            action="store",
            timestamp=datetime.now(),
        )
        assert log.action == "store"
        assert log.caller_context is None
