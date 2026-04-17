"""scripts/rotate_master_key.py — Master key rotation for FernetPostgresVault.

Re-encrypts every row in `tenant_secrets` from OLD_KEY to NEW_KEY in a single
transaction. All-or-nothing: if any row fails, the transaction is rolled back and
the database is left unchanged.

Usage::

    OLD_KEY="<current VAULT_MASTER_KEY>" \\
    NEW_KEY="<new Fernet key>" \\
    DATABASE_URL="postgresql+asyncpg://..." \\
    uv run python scripts/rotate_master_key.py

Generate a new key::

    uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'

WARNING:
    Do NOT set VAULT_MASTER_KEY to the new key before this script exits
    successfully. Partial rotation leaves the database in a mixed-ciphertext
    state where some rows decrypt with the old key and some with the new key.
    The script reads OLD_KEY and NEW_KEY from dedicated env vars — not from
    VAULT_MASTER_KEY — to prevent accidental self-corruption.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Environment variable loading — explicit and verbose
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    """Return the value of an env var or abort with a clear error message."""
    value = os.getenv(name)
    if not value:
        print(f"ERROR: {name} environment variable is required but not set.", file=sys.stderr)
        sys.exit(1)
    return value


def _load_fernet(key_env_name: str, raw_key: str) -> Fernet:
    """Parse a Fernet key string or abort with a clear error message."""
    try:
        return Fernet(raw_key.encode() if isinstance(raw_key, str) else raw_key)
    except Exception as exc:
        print(
            f"ERROR: {key_env_name} is not a valid Fernet key: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Rotation logic — single async transaction
# ---------------------------------------------------------------------------


async def rotate_keys(
    database_url: str,
    old_fernet: Fernet,
    new_fernet: Fernet,
) -> None:
    """Re-encrypt all tenant_secrets rows from old_fernet to new_fernet.

    Runs inside a single BEGIN ... COMMIT transaction. Any failure triggers
    ROLLBACK — the database is left unchanged.

    Args:
        database_url: SQLAlchemy async connection string.
        old_fernet: Fernet instance initialised with the CURRENT master key.
        new_fernet: Fernet instance initialised with the NEW master key.

    Raises:
        SystemExit(1): on any decryption or DB error (after rollback).
    """
    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    rotated_count = 0
    tenant_set: set[str] = set()

    async with session_factory() as session:
        async with session.begin():
            # Fetch all secrets — load the full rows so we can update them
            result = await session.execute(
                text(
                    "SELECT id, tenant_id, key_name, ciphertext FROM tenant_secrets"
                    " ORDER BY tenant_id, key_name"
                )
            )
            rows = result.fetchall()

            total = len(rows)
            print(f"Found {total} secrets to rotate.")

            for row in rows:
                secret_id, tenant_id, key_name, ciphertext = row

                # Convert memoryview → bytes if asyncpg returns memoryview for BYTEA
                if isinstance(ciphertext, memoryview):
                    ciphertext = bytes(ciphertext)

                print(f"  Rotating tenant={tenant_id} key={key_name} ... ", end="", flush=True)

                # Decrypt with OLD key
                try:
                    plaintext_bytes = old_fernet.decrypt(ciphertext)
                except InvalidToken as exc:
                    print("FAIL")
                    print(
                        f"ERROR rotating secret '{key_name}' for tenant {tenant_id}: "
                        f"decryption failed — wrong OLD_KEY or corrupted ciphertext: {exc}",
                        file=sys.stderr,
                    )
                    print(
                        "Transaction rolled back. Database unchanged. "
                        "Do NOT update VAULT_MASTER_KEY.",
                        file=sys.stderr,
                    )
                    # Raising inside session.begin() triggers automatic ROLLBACK
                    raise

                # Re-encrypt with NEW key
                new_ciphertext = new_fernet.encrypt(plaintext_bytes)

                # Update the row in-place — set rotated_at to signal the rotation
                now_utc = datetime.now(tz=timezone.utc)
                await session.execute(
                    text(
                        "UPDATE tenant_secrets"
                        " SET ciphertext = :ciphertext, rotated_at = :rotated_at"
                        " WHERE id = :id"
                    ),
                    {
                        "ciphertext": new_ciphertext,
                        "rotated_at": now_utc,
                        "id": secret_id,
                    },
                )

                rotated_count += 1
                tenant_set.add(str(tenant_id))
                print("OK")

            # Commit happens automatically when exiting session.begin() without error

    await engine.dispose()

    print(
        f"\nRotated {rotated_count} secrets across {len(tenant_set)} tenants. "
        "Transaction committed. Safe to update VAULT_MASTER_KEY."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point — reads env vars, validates keys, runs rotation."""
    database_url = _require_env("DATABASE_URL")
    old_key_raw = _require_env("OLD_KEY")
    new_key_raw = _require_env("NEW_KEY")

    if old_key_raw == new_key_raw:
        print("ERROR: OLD_KEY and NEW_KEY are identical. Nothing to rotate.", file=sys.stderr)
        sys.exit(1)

    print("Loading and validating Fernet keys...")
    old_fernet = _load_fernet("OLD_KEY", old_key_raw)
    new_fernet = _load_fernet("NEW_KEY", new_key_raw)
    print("Keys are valid Fernet keys.")

    print(f"Connecting to database: {database_url[:40]}...")

    try:
        asyncio.run(rotate_keys(database_url, old_fernet, new_fernet))
    except Exception as exc:
        # Only reached if error propagated past asyncio.run — already logged above
        print(f"Rotation aborted: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
