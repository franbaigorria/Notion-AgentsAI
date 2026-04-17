"""Tests para build_tenant_context_from_env() — Task 4.4 (RED) y Task 4.5 (GREEN).

Verifica:
- Cuando USE_TENANT_REGISTRY no está seteado o es distinto de "true": retorna None
- Cuando USE_TENANT_REGISTRY=true: llama al registry y retorna TenantContext
- Cuando USE_TENANT_REGISTRY=true y tenant no existe: propaga TenantNotFound
- Cuando USE_TENANT_REGISTRY=true y tenant disabled: propaga TenantDisabled
- El vault NO es llamado durante la construcción del contexto
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from core.tenants.base import Tenant, TenantDisabled, TenantId, TenantNotFound
from core.vault.base import CredentialVault
from core.orchestrator.tenant_context import TenantContext

# ---------------------------------------------------------------------------
# Import bajo test — falla hasta Task 4.5 (GREEN)
# ---------------------------------------------------------------------------

from core.orchestrator.agent import build_tenant_context_from_env


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_tenant() -> Tenant:
    tid = TenantId(UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
    return Tenant(id=tid, name="Clínica Demo", vertical="clinica")


def make_mock_registry(tenant: Tenant) -> MagicMock:
    registry = MagicMock()
    registry.get = AsyncMock(return_value=tenant)
    return registry


def make_mock_vault() -> MagicMock:
    vault = MagicMock(spec=CredentialVault)
    vault.get = AsyncMock(return_value="secret")
    return vault


# ---------------------------------------------------------------------------
# Feature flag OFF — retorna None sin llamar al registry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_none_when_flag_unset(monkeypatch):
    """Sin USE_TENANT_REGISTRY, la función retorna None."""
    monkeypatch.delenv("USE_TENANT_REGISTRY", raising=False)

    tenant = make_tenant()
    registry = make_mock_registry(tenant)
    vault = make_mock_vault()

    result = await build_tenant_context_from_env(
        tenant_id=tenant.id,
        registry=registry,
        vault=vault,
    )

    assert result is None
    registry.get.assert_not_called()


@pytest.mark.asyncio
async def test_returns_none_when_flag_is_false(monkeypatch):
    """USE_TENANT_REGISTRY=false → retorna None."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "false")

    tenant = make_tenant()
    registry = make_mock_registry(tenant)
    vault = make_mock_vault()

    result = await build_tenant_context_from_env(
        tenant_id=tenant.id,
        registry=registry,
        vault=vault,
    )

    assert result is None
    registry.get.assert_not_called()


@pytest.mark.asyncio
async def test_returns_none_when_flag_is_zero(monkeypatch):
    """USE_TENANT_REGISTRY=0 → retorna None (solo 'true' activa el flag)."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "0")

    tenant = make_tenant()
    registry = make_mock_registry(tenant)
    vault = make_mock_vault()

    result = await build_tenant_context_from_env(
        tenant_id=tenant.id,
        registry=registry,
        vault=vault,
    )

    assert result is None
    registry.get.assert_not_called()


# ---------------------------------------------------------------------------
# Feature flag ON — llama al registry y retorna TenantContext
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_tenant_context_when_flag_true(monkeypatch):
    """USE_TENANT_REGISTRY=true → retorna TenantContext con el tenant."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "true")

    tenant = make_tenant()
    registry = make_mock_registry(tenant)
    vault = make_mock_vault()

    result = await build_tenant_context_from_env(
        tenant_id=tenant.id,
        registry=registry,
        vault=vault,
    )

    assert isinstance(result, TenantContext)
    assert result.tenant == tenant
    assert result.vault is vault


@pytest.mark.asyncio
async def test_calls_registry_get_when_flag_true(monkeypatch):
    """Con flag=true, registry.get() debe llamarse exactamente una vez."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "true")

    tenant = make_tenant()
    registry = make_mock_registry(tenant)
    vault = make_mock_vault()

    await build_tenant_context_from_env(
        tenant_id=tenant.id,
        registry=registry,
        vault=vault,
    )

    registry.get.assert_called_once_with(tenant.id)


@pytest.mark.asyncio
async def test_vault_not_called_during_build_with_flag_true(monkeypatch):
    """El vault NO debe llamarse durante la construcción (acceso lazy)."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "true")

    tenant = make_tenant()
    registry = make_mock_registry(tenant)
    vault = make_mock_vault()

    await build_tenant_context_from_env(
        tenant_id=tenant.id,
        registry=registry,
        vault=vault,
    )

    vault.get.assert_not_called()


# ---------------------------------------------------------------------------
# Feature flag ON — propagación de excepciones
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_propagates_tenant_not_found_when_flag_true(monkeypatch):
    """TenantNotFound desde el registry se propaga — no se silencia."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "true")

    tid = TenantId(UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"))
    registry = MagicMock()
    registry.get = AsyncMock(side_effect=TenantNotFound("not found"))
    vault = make_mock_vault()

    with pytest.raises(TenantNotFound):
        await build_tenant_context_from_env(
            tenant_id=tid,
            registry=registry,
            vault=vault,
        )


@pytest.mark.asyncio
async def test_propagates_tenant_disabled_when_flag_true(monkeypatch):
    """TenantDisabled desde el registry se propaga — no se silencia."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "true")

    tid = TenantId(UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"))
    registry = MagicMock()
    registry.get = AsyncMock(side_effect=TenantDisabled("disabled"))
    vault = make_mock_vault()

    with pytest.raises(TenantDisabled):
        await build_tenant_context_from_env(
            tenant_id=tid,
            registry=registry,
            vault=vault,
        )
