"""scripts/seed_tenant.py — Seed a tenant + credentials for Railway (or any Postgres).

Creates or idempotently updates a tenant via ``PostgresTenantRegistry`` and stores
N provider secrets via ``FernetPostgresVault``. All inputs come from the CLI or
environment — the script does NOT read config files or interactive prompts.

Idempotency:
  - If ``--tenant-id <UUID>`` is provided AND the tenant exists, it is updated
    (name/vertical patched, ``updated_at`` refreshed). Secrets are upserted
    (``vault.store`` replaces existing ciphertext atomically).
  - If ``--tenant-id`` is provided AND the tenant does NOT exist, a new row is
    created with that id.
  - If ``--tenant-id`` is omitted, a fresh UUID is generated and a new tenant
    is created.

Usage::

    export DATABASE_URL="postgresql://user:pw@host:5432/db"   # or asyncpg://
    export VAULT_MASTER_KEY="<fernet key>"

    uv run python scripts/seed_tenant.py \\
      --name "Clinica Demo" \\
      --vertical clinica \\
      --secret deepgram=<key> \\
      --secret claude=<key> \\
      --secret elevenlabs=<key>

    # Idempotent re-run — update + re-store secrets:
    uv run python scripts/seed_tenant.py \\
      --name "Clinica Demo v2" \\
      --vertical clinica \\
      --tenant-id <uuid from first run> \\
      --secret deepgram=<rotated key>

Exit codes:
  0 — success
  1 — env var missing or argparse validation error
  2 — runtime error talking to Postgres / vault

Shell-history note: ``--secret`` values land in shell history. Prefix the command
with a space (when ``HISTCONTROL=ignorespace``) or run ``history -d`` afterwards.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from core.tenants.postgres import PostgresTenantRegistry
    from core.vault.fernet_postgres import FernetPostgresVault


# ---------------------------------------------------------------------------
# Env helpers
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    """Return env var value or exit 1 with a descriptive error."""
    value = os.getenv(name)
    if not value:
        print(f"ERROR: {name} environment variable is required but not set.", file=sys.stderr)
        sys.exit(1)
    return value


# ---------------------------------------------------------------------------
# Argparse helpers
# ---------------------------------------------------------------------------


def _parse_secret_arg(raw: str) -> tuple[str, str]:
    """Parse a ``KEY=VALUE`` string. Value may contain ``=``. Empty sides rejected."""
    if "=" not in raw:
        raise argparse.ArgumentTypeError(
            f"Secret must be in KEY=VALUE format, got {raw!r}"
        )
    key, value = raw.split("=", 1)
    if not key:
        raise argparse.ArgumentTypeError(f"Secret KEY must be non-empty, got {raw!r}")
    if not value:
        raise argparse.ArgumentTypeError(f"Secret VALUE must be non-empty, got {raw!r}")
    return key, value


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args. Returns argparse.Namespace with typed fields."""
    parser = argparse.ArgumentParser(
        prog="seed_tenant",
        description="Create or update a tenant and store provider credentials in the vault.",
    )
    parser.add_argument("--name", required=True, help="Human-readable tenant name")
    parser.add_argument(
        "--vertical",
        required=True,
        help="Business vertical — must match a verticals/ config (e.g. 'clinica')",
    )
    parser.add_argument(
        "--tenant-id",
        type=uuid.UUID,
        default=None,
        help="Existing tenant UUID for idempotent upsert. Omit to generate a new one.",
    )
    parser.add_argument(
        "--secret",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        type=_parse_secret_arg,
        help="Provider secret to store in the vault. Repeatable. E.g. --secret deepgram=abc",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Async helpers — factored out so tests can patch them cleanly
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _open_registry() -> AsyncIterator[PostgresTenantRegistry]:
    """Yield a PostgresTenantRegistry bound to a fresh transactional session."""
    from core.db.engine import get_session
    from core.tenants.postgres import PostgresTenantRegistry

    async with get_session() as session:
        yield PostgresTenantRegistry(session)


def _open_vault() -> FernetPostgresVault:
    """Return a FernetPostgresVault instance (manages its own sessions internally)."""
    from core.vault.fernet_postgres import FernetPostgresVault

    return FernetPostgresVault(caller_context="seed_tenant_script")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


async def seed_tenant(
    name: str,
    vertical: str,
    tenant_id: uuid.UUID | None,
    secrets: list[tuple[str, str]],
) -> uuid.UUID:
    """Create-or-update a tenant, then store/upsert all secrets. Returns final tenant_id."""
    from core.tenants.base import Tenant, TenantId, TenantNotFound

    effective_id = TenantId(tenant_id) if tenant_id else TenantId(uuid.uuid4())

    async with _open_registry() as registry:
        if tenant_id is not None:
            try:
                updated = await registry.update(
                    effective_id,
                    {"name": name, "vertical": vertical},
                )
                print(f"Updated tenant id={updated.id} name={updated.name}")
            except TenantNotFound:
                created = await registry.create(
                    Tenant(id=effective_id, name=name, vertical=vertical)
                )
                print(f"Created tenant id={created.id} name={created.name}")
        else:
            created = await registry.create(
                Tenant(id=effective_id, name=name, vertical=vertical)
            )
            effective_id = created.id
            print(f"Created tenant id={created.id} name={created.name}")

    if secrets:
        vault = _open_vault()
        for key, value in secrets:
            await vault.store(effective_id, key, value)
            print(f"Stored secret '{key}' (value hidden)")

    return effective_id


def main() -> None:
    """Entry point — parse args, check env, run seeding."""
    args = _parse_args()
    _require_env("DATABASE_URL")
    _require_env("VAULT_MASTER_KEY")

    try:
        final_id = asyncio.run(
            seed_tenant(
                name=args.name,
                vertical=args.vertical,
                tenant_id=args.tenant_id,
                secrets=args.secret,
            )
        )
        print(f"\nOK Seeded tenant {final_id}")
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
