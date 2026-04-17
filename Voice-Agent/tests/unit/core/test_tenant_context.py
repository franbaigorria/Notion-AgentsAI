"""Tests para TenantContext — Task 4.2 (RED) y Task 4.3 (GREEN).

Verifica:
- TenantContext es un dataclass frozen con tenant: Tenant y vault: CredentialVault
- get_secret() delega a vault.get(tenant.id, key_name) — acceso lazy
- TenantNotFound / TenantDisabled se propagan desde build_tenant_context
- La firma de build_tenant_context es correcta
"""

from __future__ import annotations

import pytest
from dataclasses import fields
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from core.tenants.base import Tenant, TenantDisabled, TenantId, TenantNotFound
from core.vault.base import CredentialVault


# ---------------------------------------------------------------------------
# Imports bajo test — fallarán con ImportError hasta Task 4.3 (GREEN)
# ---------------------------------------------------------------------------

from core.orchestrator.tenant_context import TenantContext, build_tenant_context


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_tenant(status: str = "active") -> Tenant:
    tid = TenantId(UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
    return Tenant(id=tid, name="Clínica Demo", vertical="clinica", status=status)


def make_mock_vault() -> MagicMock:
    """Vault mock — get() retorna un string."""
    vault = MagicMock(spec=CredentialVault)
    vault.get = AsyncMock(return_value="secret-value")
    return vault


# ---------------------------------------------------------------------------
# TenantContext — estructura del dataclass
# ---------------------------------------------------------------------------


def test_tenant_context_is_dataclass():
    """TenantContext debe ser un dataclass."""
    import dataclasses
    assert dataclasses.is_dataclass(TenantContext)


def test_tenant_context_is_frozen():
    """TenantContext debe ser frozen (inmutable una vez creado)."""
    tenant = make_tenant()
    vault = make_mock_vault()
    ctx = TenantContext(tenant=tenant, vault=vault)

    with pytest.raises((AttributeError, TypeError)):
        ctx.tenant = make_tenant()  # type: ignore[misc]


def test_tenant_context_has_tenant_field():
    field_names = {f.name for f in fields(TenantContext)}
    assert "tenant" in field_names


def test_tenant_context_has_vault_field():
    field_names = {f.name for f in fields(TenantContext)}
    assert "vault" in field_names


def test_tenant_context_construction():
    """TenantContext se construye correctamente con tenant y vault."""
    tenant = make_tenant()
    vault = make_mock_vault()
    ctx = TenantContext(tenant=tenant, vault=vault)

    assert ctx.tenant is tenant
    assert ctx.vault is vault


# ---------------------------------------------------------------------------
# TenantContext.get_secret() — acceso lazy al vault
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_secret_delegates_to_vault():
    """get_secret() debe delegar a vault.get(tenant.id, key_name)."""
    tenant = make_tenant()
    vault = make_mock_vault()
    vault.get = AsyncMock(return_value="my-api-key")

    ctx = TenantContext(tenant=tenant, vault=vault)
    result = await ctx.get_secret("api_key")

    assert result == "my-api-key"
    vault.get.assert_called_once_with(tenant.id, "api_key")


@pytest.mark.asyncio
async def test_get_secret_uses_correct_tenant_id():
    """get_secret() usa el tenant.id del dataclass, no un argumento externo."""
    tid = TenantId(UUID("11111111-2222-3333-4444-555555555555"))
    tenant = Tenant(id=tid, name="Otro Tenant", vertical="legal")
    vault = make_mock_vault()
    vault.get = AsyncMock(return_value="val")

    ctx = TenantContext(tenant=tenant, vault=vault)
    await ctx.get_secret("some_key")

    vault.get.assert_called_once_with(tid, "some_key")


@pytest.mark.asyncio
async def test_get_secret_vault_not_called_at_construction():
    """El vault NO se llama al construir TenantContext — sólo en get_secret()."""
    tenant = make_tenant()
    vault = make_mock_vault()

    # Construction — vault.get must NOT be called
    _ctx = TenantContext(tenant=tenant, vault=vault)

    vault.get.assert_not_called()


# ---------------------------------------------------------------------------
# build_tenant_context() — factory async
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_tenant_context_returns_tenant_context():
    """build_tenant_context() retorna un TenantContext cuando el tenant existe."""
    tenant = make_tenant()
    registry = MagicMock()
    registry.get = AsyncMock(return_value=tenant)
    vault = make_mock_vault()

    ctx = await build_tenant_context(tenant.id, registry=registry, vault=vault)

    assert isinstance(ctx, TenantContext)
    assert ctx.tenant == tenant
    assert ctx.vault is vault


@pytest.mark.asyncio
async def test_build_tenant_context_calls_registry_get():
    """build_tenant_context() llama a registry.get(tenant_id)."""
    tenant = make_tenant()
    registry = MagicMock()
    registry.get = AsyncMock(return_value=tenant)
    vault = make_mock_vault()

    await build_tenant_context(tenant.id, registry=registry, vault=vault)

    registry.get.assert_called_once_with(tenant.id)


@pytest.mark.asyncio
async def test_build_tenant_context_propagates_tenant_not_found():
    """Si registry.get() lanza TenantNotFound, debe propagarse."""
    tid = TenantId(UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"))
    registry = MagicMock()
    registry.get = AsyncMock(side_effect=TenantNotFound("not found"))
    vault = make_mock_vault()

    with pytest.raises(TenantNotFound):
        await build_tenant_context(tid, registry=registry, vault=vault)


@pytest.mark.asyncio
async def test_build_tenant_context_propagates_tenant_disabled():
    """Si registry.get() lanza TenantDisabled, debe propagarse."""
    tid = TenantId(UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"))
    registry = MagicMock()
    registry.get = AsyncMock(side_effect=TenantDisabled("disabled"))
    vault = make_mock_vault()

    with pytest.raises(TenantDisabled):
        await build_tenant_context(tid, registry=registry, vault=vault)


@pytest.mark.asyncio
async def test_build_tenant_context_vault_not_called_during_build():
    """El vault NO debe ser llamado durante build_tenant_context() — acceso lazy."""
    tenant = make_tenant()
    registry = MagicMock()
    registry.get = AsyncMock(return_value=tenant)
    vault = make_mock_vault()

    await build_tenant_context(tenant.id, registry=registry, vault=vault)

    vault.get.assert_not_called()
    vault.store.assert_not_called() if hasattr(vault, "store") else None
