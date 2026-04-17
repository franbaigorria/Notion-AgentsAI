"""core.vault — CredentialVault ABC and FernetPostgresVault adapter.

Public API:
    CredentialVault     — abstract base class for all vault adapters
    FernetPostgresVault — Fernet-encrypted secrets backed by Postgres
    VaultAccessLog      — dataclass for audit log entries
    SecretNotFound      — raised when a key doesn't exist for a tenant
    VaultDecryptError   — raised on Fernet decryption failure
    CrossTenantAccessError — raised on detected cross-tenant access attempt
    MasterKeyMissingError  — raised when VAULT_MASTER_KEY env var is absent
"""

from core.vault.base import (
    CredentialVault,
    CrossTenantAccessError,
    MasterKeyMissingError,
    SecretNotFound,
    VaultAccessLog,
    VaultDecryptError,
)
from core.vault.fernet_postgres import FernetPostgresVault

__all__ = [
    "CredentialVault",
    "CrossTenantAccessError",
    "FernetPostgresVault",
    "MasterKeyMissingError",
    "SecretNotFound",
    "VaultAccessLog",
    "VaultDecryptError",
]
