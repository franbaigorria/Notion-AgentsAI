"""Integration tests for PostgresTenantRegistry.

Task 2.5 (RED): These tests FAIL until PostgresTenantRegistry is written (Task 2.6 GREEN).
Task 2.6 (GREEN): After implementation, all tests should pass against real Postgres.

Requirements:
  - Postgres running on port 55432 (docker compose up -d postgres).
  - Tests are marked @pytest.mark.integration — skipped if DB unavailable.

Test coverage:
  - create + get round-trip
  - update partial fields
  - disable (soft-delete) → get raises TenantDisabled
  - list(vertical=...) filter
  - TenantNotFound on unknown id
  - TenantDisabled on get-of-disabled
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.tenants.base import Tenant, TenantDisabled, TenantId, TenantNotFound
from core.tenants.postgres import PostgresTenantRegistry


pytestmark = pytest.mark.integration


def _make_tenant(vertical: str = "dental") -> Tenant:
    return Tenant(
        id=TenantId(uuid4()),
        name=f"Test Tenant {uuid4().hex[:8]}",
        vertical=vertical,
    )


# ---------------------------------------------------------------------------
# create + get
# ---------------------------------------------------------------------------


async def test_create_and_get_round_trip(db_session: AsyncSession):
    registry = PostgresTenantRegistry(session=db_session)
    tenant = _make_tenant()

    created = await registry.create(tenant)

    assert created.id == tenant.id
    assert created.name == tenant.name
    assert created.vertical == tenant.vertical
    assert created.config == {}
    assert created.status == "active"
    assert created.created_at is not None
    assert created.updated_at is not None

    fetched = await registry.get(tenant.id)
    assert fetched is not None
    assert fetched.id == tenant.id
    assert fetched.name == tenant.name


async def test_create_with_config(db_session: AsyncSession):
    registry = PostgresTenantRegistry(session=db_session)
    config = {"theme": "dark", "max_sessions": 10}
    tenant = Tenant(id=TenantId(uuid4()), name=f"Cfg-{uuid4().hex[:6]}", vertical="legal", config=config)

    created = await registry.create(tenant)
    fetched = await registry.get(created.id)

    assert fetched is not None
    assert fetched.config == config


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


async def test_update_changes_vertical(db_session: AsyncSession):
    registry = PostgresTenantRegistry(session=db_session)
    tenant = _make_tenant(vertical="dental")
    created = await registry.create(tenant)

    updated = await registry.update(created.id, {"vertical": "legal"})

    assert updated.vertical == "legal"
    assert updated.name == created.name  # unchanged


async def test_update_changes_config(db_session: AsyncSession):
    registry = PostgresTenantRegistry(session=db_session)
    tenant = _make_tenant()
    created = await registry.create(tenant)

    new_config = {"api_key": "abc123", "timeout": 30}
    updated = await registry.update(created.id, {"config": new_config})

    assert updated.config == new_config


async def test_update_raises_not_found_for_unknown_id(db_session: AsyncSession):
    registry = PostgresTenantRegistry(session=db_session)
    unknown_id = TenantId(uuid4())

    with pytest.raises(TenantNotFound):
        await registry.update(unknown_id, {"vertical": "legal"})


# ---------------------------------------------------------------------------
# disable
# ---------------------------------------------------------------------------


async def test_disable_prevents_get(db_session: AsyncSession):
    registry = PostgresTenantRegistry(session=db_session)
    tenant = _make_tenant()
    created = await registry.create(tenant)

    await registry.disable(created.id)

    with pytest.raises(TenantDisabled):
        await registry.get(created.id)


async def test_disable_does_not_delete_row(db_session: AsyncSession):
    """Row must still exist in DB after disable (soft-delete verification)."""
    from sqlalchemy import select

    from core.db.models import TenantORM

    registry = PostgresTenantRegistry(session=db_session)
    tenant = _make_tenant()
    created = await registry.create(tenant)

    await registry.disable(created.id)

    # Direct DB query bypassing registry to confirm row exists with status=disabled
    result = await db_session.execute(
        select(TenantORM).where(TenantORM.id == created.id)
    )
    orm_row = result.scalar_one_or_none()
    assert orm_row is not None
    assert orm_row.status == "disabled"


async def test_disable_raises_not_found_for_unknown_id(db_session: AsyncSession):
    registry = PostgresTenantRegistry(session=db_session)
    unknown_id = TenantId(uuid4())

    with pytest.raises(TenantNotFound):
        await registry.disable(unknown_id)


# ---------------------------------------------------------------------------
# get — error cases
# ---------------------------------------------------------------------------


async def test_get_raises_tenant_not_found_for_unknown_id(db_session: AsyncSession):
    registry = PostgresTenantRegistry(session=db_session)
    unknown_id = TenantId(uuid4())

    with pytest.raises(TenantNotFound):
        await registry.get(unknown_id)


async def test_get_raises_tenant_disabled_for_disabled_tenant(db_session: AsyncSession):
    registry = PostgresTenantRegistry(session=db_session)
    tenant = _make_tenant()
    created = await registry.create(tenant)
    await registry.disable(created.id)

    with pytest.raises(TenantDisabled):
        await registry.get(created.id)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


async def test_list_returns_only_active_tenants(db_session: AsyncSession):
    registry = PostgresTenantRegistry(session=db_session)
    active = await registry.create(_make_tenant(vertical="dental"))
    disabled = await registry.create(_make_tenant(vertical="dental"))
    await registry.disable(disabled.id)

    results = await registry.list()

    ids = [t.id for t in results]
    assert active.id in ids
    assert disabled.id not in ids


async def test_list_filters_by_vertical(db_session: AsyncSession):
    registry = PostgresTenantRegistry(session=db_session)
    dental1 = await registry.create(_make_tenant(vertical="dental"))
    dental2 = await registry.create(_make_tenant(vertical="dental"))
    legal1 = await registry.create(_make_tenant(vertical="legal"))

    dental_results = await registry.list(vertical="dental")
    legal_results = await registry.list(vertical="legal")

    dental_ids = [t.id for t in dental_results]
    legal_ids = [t.id for t in legal_results]

    assert dental1.id in dental_ids
    assert dental2.id in dental_ids
    assert legal1.id not in dental_ids
    assert legal1.id in legal_ids


async def test_list_no_filter_returns_all_active(db_session: AsyncSession):
    registry = PostgresTenantRegistry(session=db_session)
    t1 = await registry.create(_make_tenant(vertical="dental"))
    t2 = await registry.create(_make_tenant(vertical="legal"))
    t3 = await registry.create(_make_tenant(vertical="real_estate"))

    results = await registry.list()
    ids = [t.id for t in results]

    assert t1.id in ids
    assert t2.id in ids
    assert t3.id in ids


async def test_list_empty_returns_empty_list(db_session: AsyncSession):
    registry = PostgresTenantRegistry(session=db_session)
    results = await registry.list()
    assert results == []
