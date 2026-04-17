"""FernetPostgresVault — Fernet-encrypted credential vault backed by Postgres.

Architecture:
  - Implements CredentialVault ABC from core.vault.base
  - Encrypts every secret with Fernet (AES-128-CBC + HMAC-SHA256)
  - Stores ciphertext as BYTEA in the `tenant_secrets` table
  - Appends an audit row to `vault_audit_log` on EVERY operation
  - Master key loaded exclusively from VAULT_MASTER_KEY env var at instantiation
  - Session managed internally via a session_factory (injected or defaulting to get_session)

Security invariants:
  - Plaintext values are NEVER logged
  - Ciphertext bytes are NEVER logged
  - vault_audit_log is APPEND-ONLY — no UPDATE or DELETE methods are exposed
  - Every query on tenant_secrets filters by tenant_id (cross-tenant isolation)

Usage::

    import os
    os.environ["VAULT_MASTER_KEY"] = "..."  # Fernet key

    vault = FernetPostgresVault(caller_context="knowledge_provider")
    await vault.store(tenant_id, "gcal_token", raw_token)
    token = await vault.get(tenant_id, "gcal_token")
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import TenantSecretORM, VaultAuditLogORM
from core.tenants.base import TenantId
from core.vault.base import (
    CredentialVault,
    MasterKeyMissingError,
    SecretNotFound,
    VaultDecryptError,
)


def _default_session_factory() -> Callable:
    """Return get_session from core.db.engine.

    Imported lazily to avoid circular imports and allow test injection.
    """
    from core.db.engine import get_session

    return get_session


class FernetPostgresVault(CredentialVault):
    """Fernet-encrypted credential vault backed by Postgres.

    Instantiation fails fast if VAULT_MASTER_KEY is absent or invalid.

    Sessions are managed internally via a `session_factory` — an async context
    manager factory that yields an AsyncSession. This makes the public API match
    the CredentialVault ABC exactly (no `session=` kwarg exposure) while still
    allowing full dependency injection in tests via `session_factory`.

    APPEND-ONLY AUDIT LOG GUARANTEE:
        This class does NOT expose any method to UPDATE or DELETE rows in
        vault_audit_log. Every vault operation produces exactly one INSERT.
        Two successive store() calls for the same key produce TWO audit rows —
        the first for the insert, the second for the upsert — never one
        updated row.

    Cross-tenant isolation:
        Every SELECT on tenant_secrets includes WHERE tenant_id = :tenant_id.
        There is no code path that returns data from a different tenant_id
        than the one passed as argument.

    Args:
        master_key: Optional Fernet key string. Falls back to VAULT_MASTER_KEY env var.
        caller_context: Optional label recorded in the audit log for every operation.
        session_factory: Optional async context manager factory that yields AsyncSession.
                         Defaults to core.db.engine.get_session (production singleton).
                         Inject a test factory in tests to avoid real DB calls.
    """

    def __init__(
        self,
        *,
        master_key: str | None = None,
        caller_context: str | None = None,
        session_factory: Callable | None = None,
    ) -> None:
        _env = os.getenv("ENV", "production")
        _raw_key = master_key or os.getenv("VAULT_MASTER_KEY")

        if _raw_key is None:
            if _env != "test":
                raise MasterKeyMissingError(
                    "VAULT_MASTER_KEY environment variable is required but not set. "
                    "Generate a key with: "
                    "python -c 'from cryptography.fernet import Fernet; "
                    "print(Fernet.generate_key().decode())'"
                )
            # In test mode without a key we cannot encrypt — raise as well
            raise MasterKeyMissingError(
                "VAULT_MASTER_KEY must be set even in test mode to instantiate "
                "FernetPostgresVault. Use ENV=test + a real Fernet key in tests."
            )

        try:
            self._fernet = Fernet(_raw_key.encode() if isinstance(_raw_key, str) else _raw_key)
        except Exception as exc:
            raise MasterKeyMissingError(
                f"VAULT_MASTER_KEY is not a valid Fernet key: {exc}"
            ) from exc

        self._caller_context = caller_context
        # Defer resolution of default factory so DB env vars aren't required at import time.
        self._session_factory = session_factory or _default_session_factory()

    # -------------------------------------------------------------------------
    # Encryption helpers (internal — not part of ABC public API)
    # -------------------------------------------------------------------------

    def _encrypt(self, plaintext: str) -> bytes:
        """Encrypt a plaintext string and return Fernet ciphertext bytes."""
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def _decrypt(self, ciphertext: bytes) -> str:
        """Decrypt Fernet ciphertext bytes and return plaintext string.

        Raises:
            VaultDecryptError: if the ciphertext is invalid or the key mismatches.
        """
        try:
            return self._fernet.decrypt(ciphertext).decode("utf-8")
        except (InvalidToken, Exception) as exc:
            raise VaultDecryptError(
                "Failed to decrypt secret — key mismatch or corrupted ciphertext."
            ) from exc

    # -------------------------------------------------------------------------
    # Audit log helper (internal — NEVER exposed publicly)
    # -------------------------------------------------------------------------

    def _audit(
        self,
        session: AsyncSession,
        tenant_id: TenantId,
        key_name: str,
        action: str,
    ) -> None:
        """Append one row to vault_audit_log via session.add (INSERT only).

        This is the ONLY write path to vault_audit_log. No UPDATE or DELETE.
        """
        log_row = VaultAuditLogORM(
            tenant_id=tenant_id,
            key_name=key_name,
            action=action,
            caller_context=self._caller_context,
            timestamp=datetime.now(tz=timezone.utc),
        )
        session.add(log_row)

    # -------------------------------------------------------------------------
    # CredentialVault ABC implementation
    # -------------------------------------------------------------------------

    async def store(
        self,
        tenant_id: TenantId,
        key_name: str,
        value: str,
    ) -> None:
        """Encrypt and upsert a secret for the tenant. Audit: action='store'.

        If a secret with key_name already exists for this tenant, its ciphertext
        is replaced (upsert). Each call produces a new audit row — NEVER an
        updated row.

        Session is managed internally via the injected session_factory.
        The audit log row is committed atomically with the secret write.
        """
        ciphertext = self._encrypt(value)

        async with self._session_factory() as session:
            # Look up existing row (for upsert)
            result = await session.execute(
                select(TenantSecretORM).where(
                    TenantSecretORM.tenant_id == tenant_id,
                    TenantSecretORM.key_name == key_name,
                )
            )
            existing = result.scalar_one_or_none()

            if existing is not None:
                # Upsert — update ciphertext in place
                existing.ciphertext = ciphertext
                existing.rotated_at = datetime.now(tz=timezone.utc)
            else:
                # Insert new row
                secret_row = TenantSecretORM(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    key_name=key_name,
                    ciphertext=ciphertext,
                )
                session.add(secret_row)

            # Audit — ALWAYS a new INSERT (never updates existing audit rows)
            self._audit(session, tenant_id, key_name, "store")
            await session.flush()

    async def get(
        self,
        tenant_id: TenantId,
        key_name: str,
    ) -> str:
        """Retrieve and decrypt a secret for the tenant. Audit: action='get'.

        Cross-tenant isolation: the WHERE clause always includes tenant_id so
        it is impossible to retrieve another tenant's secret.

        Session is managed internally via the injected session_factory.
        The audit log row is committed atomically with the read.

        Raises:
            SecretNotFound: if the key does not exist for this tenant.
            VaultDecryptError: if the ciphertext cannot be decrypted.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(TenantSecretORM).where(
                    TenantSecretORM.tenant_id == tenant_id,
                    TenantSecretORM.key_name == key_name,
                )
            )
            secret_orm = result.scalar_one_or_none()

            if secret_orm is None:
                self._audit(session, tenant_id, key_name, "get")
                await session.flush()
                raise SecretNotFound(
                    f"Secret '{key_name}' not found for tenant {tenant_id}."
                )

            plaintext = self._decrypt(secret_orm.ciphertext)

            # Audit — ALWAYS a new INSERT
            self._audit(session, tenant_id, key_name, "get")
            await session.flush()

        return plaintext

    async def delete(
        self,
        tenant_id: TenantId,
        key_name: str,
    ) -> None:
        """Physically remove a secret for the tenant. Audit: action='delete'.

        Session is managed internally via the injected session_factory.
        The audit log row is committed atomically with the delete.

        Raises:
            SecretNotFound: if the key does not exist for this tenant.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(TenantSecretORM).where(
                    TenantSecretORM.tenant_id == tenant_id,
                    TenantSecretORM.key_name == key_name,
                )
            )
            secret_orm = result.scalar_one_or_none()

            if secret_orm is None:
                self._audit(session, tenant_id, key_name, "delete")
                await session.flush()
                raise SecretNotFound(
                    f"Secret '{key_name}' not found for tenant {tenant_id}."
                )

            await session.delete(secret_orm)

            # Audit — ALWAYS a new INSERT
            self._audit(session, tenant_id, key_name, "delete")
            await session.flush()

    async def list_keys(
        self,
        tenant_id: TenantId,
    ) -> list[str]:
        """Return key names only for the tenant. Values are NEVER returned.

        Session is managed internally via the injected session_factory.
        Audit: action='list_keys'.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(TenantSecretORM).where(
                    TenantSecretORM.tenant_id == tenant_id,
                )
            )
            rows = result.scalars().all()

            # Audit — ALWAYS a new INSERT
            self._audit(session, tenant_id, "", "list_keys")
            await session.flush()

        return [row.key_name for row in rows]
