"""scripts/sanity_tenant_vault.py — End-to-end sanity check for tenant + vault.

Tests the full path:
  1. Creates a tenant via PostgresTenantRegistry
  2. Stores a secret via FernetPostgresVault
  3. Loads a TenantContext via build_tenant_context (with USE_TENANT_REGISTRY=true)
  4. Calls vault.get() to retrieve the secret
  5. Asserts the retrieved value equals the original
  6. Cleans up (disables tenant, deletes secret)

Usage::

    export DATABASE_URL="postgresql+asyncpg://franciscobaigorria@localhost:5432/voiceagent_test"
    export VAULT_MASTER_KEY="$(uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
    uv run python scripts/sanity_tenant_vault.py

Prints "OK End-to-end sanity passed" on success.
Prints an error and exits with code 1 on failure.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

# Ensure USE_TENANT_REGISTRY is on for this script
os.environ["USE_TENANT_REGISTRY"] = "true"


async def run_sanity() -> None:
    """Run the end-to-end sanity check."""
    # -------------------------------------------------------------------
    # Validate required env vars before importing anything that checks them
    # -------------------------------------------------------------------
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        sys.exit(1)

    vault_key = os.getenv("VAULT_MASTER_KEY")
    if not vault_key:
        print("ERROR: VAULT_MASTER_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    # -------------------------------------------------------------------
    # Imports (after env vars are confirmed present)
    # -------------------------------------------------------------------
    from core.db.engine import get_session
    from core.orchestrator.agent import _tenant_registry_enabled
    from core.orchestrator.tenant_context import build_tenant_context
    from core.tenants.base import Tenant, TenantId
    from core.tenants.postgres import PostgresTenantRegistry
    from core.vault.fernet_postgres import FernetPostgresVault

    print("=== Tenant + Vault End-to-End Sanity Check ===\n")

    SECRET_KEY = "sanity_test_api_key"
    SECRET_VALUE = f"test-secret-{uuid.uuid4().hex[:8]}"
    tenant_id: TenantId | None = None

    vault = FernetPostgresVault(caller_context="sanity_script")

    # -------------------------------------------------------------------
    # Step 1: Create a tenant
    # -------------------------------------------------------------------
    print("Step 1: Creating tenant via PostgresTenantRegistry...")
    async with get_session() as session:
        registry = PostgresTenantRegistry(session)
        new_id = TenantId(uuid.uuid4())
        tenant = await registry.create(
            Tenant(
                id=new_id,
                name=f"sanity-tenant-{new_id}",
                vertical="clinic",
                config={"sanity": True},
            )
        )
        tenant_id = tenant.id
    print(f"  Created tenant id={tenant_id} name={tenant.name}")

    # -------------------------------------------------------------------
    # Step 2: Store a secret via FernetPostgresVault
    # -------------------------------------------------------------------
    print(f"\nStep 2: Storing secret '{SECRET_KEY}' via FernetPostgresVault...")
    async with get_session() as session:
        await vault.store(tenant_id, SECRET_KEY, SECRET_VALUE, session=session)
    print("  Stored secret (value hidden)")

    # -------------------------------------------------------------------
    # Step 3: Load TenantContext via build_tenant_context
    # -------------------------------------------------------------------
    print("\nStep 3: Loading TenantContext via build_tenant_context()...")
    assert _tenant_registry_enabled(), "USE_TENANT_REGISTRY must be 'true' for this step"
    async with get_session() as session:
        registry = PostgresTenantRegistry(session)
        ctx = await build_tenant_context(tenant_id, registry=registry, vault=vault)
    print(f"  TenantContext loaded: tenant.name={ctx.tenant.name}, tenant.id={ctx.tenant.id}")

    # -------------------------------------------------------------------
    # Step 4: Retrieve secret via vault.get()
    # -------------------------------------------------------------------
    print(f"\nStep 4: Retrieving secret '{SECRET_KEY}' via vault.get()...")
    async with get_session() as session:
        retrieved = await vault.get(tenant_id, SECRET_KEY, session=session)
    print("  Retrieved secret successfully (value hidden)")

    # -------------------------------------------------------------------
    # Step 5: Assert equality
    # -------------------------------------------------------------------
    print("\nStep 5: Asserting retrieved value equals original...")
    assert retrieved == SECRET_VALUE, (
        f"FAIL: retrieved value does not match original!\n"
        f"  expected: {SECRET_VALUE!r}\n"
        f"  got:      {retrieved!r}"
    )
    print("  Values match.")

    # -------------------------------------------------------------------
    # Step 6: Cleanup — disable tenant and delete secret
    # -------------------------------------------------------------------
    print("\nStep 6: Cleaning up (disabling tenant, deleting secret)...")
    async with get_session() as session:
        registry = PostgresTenantRegistry(session)
        await registry.disable(tenant_id)
        await vault.delete(tenant_id, SECRET_KEY, session=session)
    print(f"  Tenant {tenant_id} disabled. Secret '{SECRET_KEY}' deleted.")

    print("\nOK End-to-end sanity passed")


def main() -> None:
    try:
        asyncio.run(run_sanity())
    except AssertionError as exc:
        print(f"\nSANITY FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\nSANITY ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
