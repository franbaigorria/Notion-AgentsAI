"""Integration tests para orchestrator tenant integration — Task 4.6.

Verifica el path completo contra Postgres real:
- build_tenant_context_from_env() con flag ON retorna TenantContext válido
- get_secret() en TenantContext funciona de forma lazy con vault real
- TenantNotFound se propaga cuando el tenant_id no existe en DB
- Flag OFF: retorna None sin tocar Postgres

Requiere:
  - DATABASE_URL apuntando a Postgres de test
  - VAULT_MASTER_KEY con clave Fernet válida
  Ambas son seteadas por tests/integration/conftest.py.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from core.tenants.base import Tenant, TenantId, TenantNotFound
from core.tenants.postgres import PostgresTenantRegistry
from core.vault.fernet_postgres import FernetPostgresVault
from core.orchestrator.agent import build_tenant_context_from_env
from core.orchestrator.tenant_context import TenantContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def registry(db_session: AsyncSession) -> PostgresTenantRegistry:
    """Registry real apuntando a la sesión de test."""
    return PostgresTenantRegistry(session=db_session)


@pytest_asyncio.fixture
async def active_tenant(db_session: AsyncSession) -> Tenant:
    """Crea y retorna un tenant activo en la DB de test."""
    reg = PostgresTenantRegistry(session=db_session)
    tid = TenantId(uuid4())
    tenant = await reg.create(
        Tenant(
            id=tid,
            name="Clínica Orquestador Test",
            vertical="clinica",
            config={"greeting": "Hola desde tenant"},
        )
    )
    return tenant


# ---------------------------------------------------------------------------
# Tests — flag OFF (backward compat)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_flag_off_returns_none_no_db_call(
    active_tenant: Tenant,
    registry: PostgresTenantRegistry,
    vault: FernetPostgresVault,
    monkeypatch,
):
    """Flag OFF: build_tenant_context_from_env retorna None, sin tocar Postgres."""
    monkeypatch.delenv("USE_TENANT_REGISTRY", raising=False)

    result = await build_tenant_context_from_env(
        tenant_id=active_tenant.id,
        registry=registry,
        vault=vault,
    )

    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_flag_false_returns_none(
    active_tenant: Tenant,
    registry: PostgresTenantRegistry,
    vault: FernetPostgresVault,
    monkeypatch,
):
    """Flag=false: retorna None."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "false")

    result = await build_tenant_context_from_env(
        tenant_id=active_tenant.id,
        registry=registry,
        vault=vault,
    )

    assert result is None


# ---------------------------------------------------------------------------
# Tests — flag ON (multi-tenant path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_flag_on_returns_valid_tenant_context(
    active_tenant: Tenant,
    registry: PostgresTenantRegistry,
    vault: FernetPostgresVault,
    monkeypatch,
):
    """Flag ON + tenant activo → TenantContext con datos correctos desde Postgres."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "true")

    result = await build_tenant_context_from_env(
        tenant_id=active_tenant.id,
        registry=registry,
        vault=vault,
    )

    assert isinstance(result, TenantContext)
    assert result.tenant.id == active_tenant.id
    assert result.tenant.name == "Clínica Orquestador Test"
    assert result.tenant.vertical == "clinica"
    assert result.vault is vault


@pytest.mark.asyncio
@pytest.mark.integration
async def test_flag_on_tenant_context_is_frozen(
    active_tenant: Tenant,
    registry: PostgresTenantRegistry,
    vault: FernetPostgresVault,
    monkeypatch,
):
    """TenantContext resultante es frozen — no se puede mutar."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "true")

    ctx = await build_tenant_context_from_env(
        tenant_id=active_tenant.id,
        registry=registry,
        vault=vault,
    )
    assert ctx is not None

    with pytest.raises((AttributeError, TypeError)):
        ctx.tenant = active_tenant  # type: ignore[misc]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_flag_on_get_secret_lazy_fetch(
    active_tenant: Tenant,
    registry: PostgresTenantRegistry,
    vault: FernetPostgresVault,
    monkeypatch,
):
    """get_secret() en TenantContext real recupera el secreto via vault interno.

    Now that FernetPostgresVault manages its own sessions via session_factory,
    TenantContext.get_secret() works end-to-end without requiring the caller to
    pass a session. This test proves the full delegation chain is wired correctly.
    """
    monkeypatch.setenv("USE_TENANT_REGISTRY", "true")

    # Store a secret in the vault first (vault manages its own session)
    await vault.store(
        active_tenant.id,
        "test_api_key",
        "super-secret-value-123",
    )

    ctx = await build_tenant_context_from_env(
        tenant_id=active_tenant.id,
        registry=registry,
        vault=vault,
    )
    assert ctx is not None

    # Lazy fetch — vault not called during build, called now via get_secret()
    # This is the critical path that was broken (CRIT-01): vault.get() required session=
    # but TenantContext.get_secret() called vault.get(tenant_id, key_name) without it.
    # Now the vault manages its own sessions — this works correctly.
    plaintext = await ctx.get_secret("test_api_key")
    assert plaintext == "super-secret-value-123"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_flag_on_unknown_tenant_raises_tenant_not_found(
    registry: PostgresTenantRegistry,
    vault: FernetPostgresVault,
    monkeypatch,
):
    """Flag ON + tenant_id inexistente → TenantNotFound propagado, no silenciado."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "true")

    nonexistent_id = TenantId(uuid4())

    with pytest.raises(TenantNotFound):
        await build_tenant_context_from_env(
            tenant_id=nonexistent_id,
            registry=registry,
            vault=vault,
        )
