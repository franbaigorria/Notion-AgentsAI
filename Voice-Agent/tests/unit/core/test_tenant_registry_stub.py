"""Tests del contrato de TenantRegistry usando una implementación in-memory.

Task 2.3: El StubTenantRegistry vive en el mismo archivo para que el test
sea autónomo (sin Postgres). Valida que el contrato ABC sea completo y
ejercitable con los 5 métodos + los casos de error.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

from core.tenants.base import (
    Tenant,
    TenantDisabled,
    TenantId,
    TenantNotFound,
    TenantRegistry,
)


# ---------------------------------------------------------------------------
# Stub implementation — in-memory, no Postgres
# ---------------------------------------------------------------------------


class StubTenantRegistry(TenantRegistry):
    """Implementación en memoria del TenantRegistry para tests unitarios."""

    def __init__(self) -> None:
        self._store: dict[TenantId, Tenant] = {}

    async def get(self, tenant_id: TenantId) -> Tenant | None:
        tenant = self._store.get(tenant_id)
        if tenant is None:
            raise TenantNotFound(f"Tenant {tenant_id} not found")
        if tenant.status == "disabled":
            raise TenantDisabled(f"Tenant {tenant_id} is disabled")
        return tenant

    async def create(self, tenant: Tenant) -> Tenant:
        now = datetime.now(tz=timezone.utc)
        persisted = Tenant(
            id=tenant.id,
            name=tenant.name,
            vertical=tenant.vertical,
            config=tenant.config,
            status=tenant.status,
            created_at=now,
            updated_at=now,
        )
        self._store[tenant.id] = persisted
        return persisted

    async def update(self, tenant_id: TenantId, patch: dict[str, Any]) -> Tenant:
        existing = self._store.get(tenant_id)
        if existing is None:
            raise TenantNotFound(f"Tenant {tenant_id} not found")
        updated = Tenant(
            id=existing.id,
            name=patch.get("name", existing.name),
            vertical=patch.get("vertical", existing.vertical),
            config=patch.get("config", existing.config),
            status=patch.get("status", existing.status),
            created_at=existing.created_at,
            updated_at=datetime.now(tz=timezone.utc),
        )
        self._store[tenant_id] = updated
        return updated

    async def disable(self, tenant_id: TenantId) -> None:
        existing = self._store.get(tenant_id)
        if existing is None:
            raise TenantNotFound(f"Tenant {tenant_id} not found")
        self._store[tenant_id] = Tenant(
            id=existing.id,
            name=existing.name,
            vertical=existing.vertical,
            config=existing.config,
            status="disabled",
            created_at=existing.created_at,
            updated_at=datetime.now(tz=timezone.utc),
        )

    async def list(self, vertical: str | None = None) -> list[Tenant]:
        tenants = [t for t in self._store.values() if t.status == "active"]
        if vertical is not None:
            tenants = [t for t in tenants if t.vertical == vertical]
        return tenants


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_tenant(vertical: str = "dental", status: str = "active") -> Tenant:
    return Tenant(
        id=TenantId(uuid4()),
        name=f"Clínica Test {uuid4().hex[:6]}",
        vertical=vertical,
        status=status,  # type: ignore[arg-type]
    )


@pytest.fixture
def registry() -> StubTenantRegistry:
    return StubTenantRegistry()


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


async def test_create_returns_tenant_with_timestamps(registry: StubTenantRegistry):
    tenant = _make_tenant()
    result = await registry.create(tenant)
    assert result.id == tenant.id
    assert result.name == tenant.name
    assert result.created_at is not None
    assert result.updated_at is not None


async def test_create_then_get_returns_same_tenant(registry: StubTenantRegistry):
    tenant = _make_tenant()
    created = await registry.create(tenant)
    fetched = await registry.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == created.name


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


async def test_get_raises_tenant_not_found_for_unknown_id(registry: StubTenantRegistry):
    unknown_id = TenantId(uuid4())
    with pytest.raises(TenantNotFound):
        await registry.get(unknown_id)


async def test_get_raises_tenant_disabled_for_disabled_tenant(registry: StubTenantRegistry):
    tenant = _make_tenant()
    created = await registry.create(tenant)
    await registry.disable(created.id)

    with pytest.raises(TenantDisabled):
        await registry.get(created.id)


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


async def test_update_changes_specified_fields(registry: StubTenantRegistry):
    tenant = _make_tenant(vertical="dental")
    created = await registry.create(tenant)

    updated = await registry.update(created.id, {"vertical": "legal"})

    assert updated.vertical == "legal"
    assert updated.name == created.name  # unchanged


async def test_update_refreshes_updated_at(registry: StubTenantRegistry):
    tenant = _make_tenant()
    created = await registry.create(tenant)
    original_updated_at = created.updated_at

    import asyncio
    await asyncio.sleep(0.001)  # ensure clock advances
    updated = await registry.update(created.id, {"vertical": "real_estate"})

    assert updated.updated_at is not None
    assert updated.updated_at > original_updated_at  # type: ignore[operator]


async def test_update_raises_tenant_not_found_for_unknown_id(registry: StubTenantRegistry):
    unknown_id = TenantId(uuid4())
    with pytest.raises(TenantNotFound):
        await registry.update(unknown_id, {"vertical": "legal"})


# ---------------------------------------------------------------------------
# disable
# ---------------------------------------------------------------------------


async def test_disable_changes_status_to_disabled(registry: StubTenantRegistry):
    tenant = _make_tenant()
    created = await registry.create(tenant)

    await registry.disable(created.id)

    # Direct access to internal store to verify (bypasses get() guard)
    raw = registry._store[created.id]
    assert raw.status == "disabled"


async def test_disable_raises_tenant_not_found_for_unknown_id(registry: StubTenantRegistry):
    unknown_id = TenantId(uuid4())
    with pytest.raises(TenantNotFound):
        await registry.disable(unknown_id)


async def test_disable_does_not_physically_remove_tenant(registry: StubTenantRegistry):
    tenant = _make_tenant()
    created = await registry.create(tenant)

    await registry.disable(created.id)

    # Still exists in store — just disabled
    assert created.id in registry._store


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


async def test_list_returns_only_active_tenants(registry: StubTenantRegistry):
    active = _make_tenant(vertical="dental")
    disabled = _make_tenant(vertical="dental")

    created_active = await registry.create(active)
    created_disabled = await registry.create(disabled)
    await registry.disable(created_disabled.id)

    results = await registry.list()

    ids = [t.id for t in results]
    assert created_active.id in ids
    assert created_disabled.id not in ids


async def test_list_filters_by_vertical(registry: StubTenantRegistry):
    dental = _make_tenant(vertical="dental")
    legal = _make_tenant(vertical="legal")

    await registry.create(dental)
    await registry.create(legal)

    dental_results = await registry.list(vertical="dental")
    legal_results = await registry.list(vertical="legal")

    assert all(t.vertical == "dental" for t in dental_results)
    assert all(t.vertical == "legal" for t in legal_results)


async def test_list_no_filter_returns_all_active(registry: StubTenantRegistry):
    t1 = await registry.create(_make_tenant(vertical="dental"))
    t2 = await registry.create(_make_tenant(vertical="legal"))
    t3 = await registry.create(_make_tenant(vertical="real_estate"))

    results = await registry.list()

    ids = [t.id for t in results]
    assert t1.id in ids
    assert t2.id in ids
    assert t3.id in ids


async def test_list_empty_when_no_tenants(registry: StubTenantRegistry):
    results = await registry.list()
    assert results == []


async def test_list_vertical_no_match_returns_empty(registry: StubTenantRegistry):
    await registry.create(_make_tenant(vertical="dental"))
    results = await registry.list(vertical="nonexistent")
    assert results == []
