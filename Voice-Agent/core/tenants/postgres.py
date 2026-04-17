"""core.tenants.postgres — PostgresTenantRegistry adapter.

Implementa TenantRegistry contra Postgres usando SQLAlchemy 2.x async.
Recibe una AsyncSession inyectada — NO crea su propio engine.

Convención de errores:
  - get() lanza TenantNotFound si el tenant no existe.
  - get() lanza TenantDisabled si el tenant existe pero status='disabled'.
  - update() / disable() lanzan TenantNotFound si el tenant no existe.
  - No se expone hard-delete — disable() es soft-delete.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import TenantORM
from core.tenants.base import Tenant, TenantDisabled, TenantId, TenantNotFound, TenantRegistry


class PostgresTenantRegistry(TenantRegistry):
    """Adaptador de TenantRegistry contra Postgres via SQLAlchemy 2.x async.

    Args:
        session: AsyncSession inyectada desde afuera. El llamador es responsable
                 de manejar el ciclo de vida de la sesión (commit / rollback / close).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ---------------------------------------------------------------------------
    # Helpers privados
    # ---------------------------------------------------------------------------

    @staticmethod
    def _orm_to_domain(row: TenantORM) -> Tenant:
        """Convierte una fila ORM al dataclass de dominio."""
        return Tenant(
            id=TenantId(row.id),
            name=row.name,
            vertical=row.vertical,
            config=row.config or {},
            status=row.status,  # type: ignore[arg-type]
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def _get_orm_or_raise(self, tenant_id: TenantId) -> TenantORM:
        """Retorna la fila ORM o lanza TenantNotFound."""
        result = await self._session.execute(
            select(TenantORM).where(TenantORM.id == tenant_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise TenantNotFound(f"Tenant {tenant_id} not found")
        return row

    # ---------------------------------------------------------------------------
    # ABC implementation
    # ---------------------------------------------------------------------------

    async def get(self, tenant_id: TenantId) -> Tenant | None:
        """Retorna el tenant activo o lanza TenantNotFound / TenantDisabled."""
        row = await self._get_orm_or_raise(tenant_id)
        if row.status == "disabled":
            raise TenantDisabled(f"Tenant {tenant_id} is disabled")
        return self._orm_to_domain(row)

    async def create(self, tenant: Tenant) -> Tenant:
        """Persiste un nuevo tenant y retorna la entidad con timestamps."""
        now = datetime.now(tz=timezone.utc)
        row = TenantORM(
            id=tenant.id if tenant.id else uuid4(),
            name=tenant.name,
            vertical=tenant.vertical,
            config=tenant.config,
            status=tenant.status,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()  # flush to DB within the active transaction
        await self._session.refresh(row)
        return self._orm_to_domain(row)

    async def update(self, tenant_id: TenantId, patch: dict[str, Any]) -> Tenant:
        """Aplica un patch parcial al tenant y retorna la entidad actualizada."""
        row = await self._get_orm_or_raise(tenant_id)

        # Apply patch — only update allowed fields
        allowed_fields = {"name", "vertical", "config", "status"}
        for key, value in patch.items():
            if key in allowed_fields:
                setattr(row, key, value)

        row.updated_at = datetime.now(tz=timezone.utc)
        await self._session.flush()
        await self._session.refresh(row)
        return self._orm_to_domain(row)

    async def disable(self, tenant_id: TenantId) -> None:
        """Marca el tenant como disabled (soft-delete). No elimina la fila."""
        row = await self._get_orm_or_raise(tenant_id)
        row.status = "disabled"
        row.updated_at = datetime.now(tz=timezone.utc)
        await self._session.flush()

    async def list(self, vertical: str | None = None) -> list[Tenant]:
        """Lista todos los tenants activos, opcionalmente filtrados por vertical."""
        stmt = select(TenantORM).where(TenantORM.status == "active")
        if vertical is not None:
            stmt = stmt.where(TenantORM.vertical == vertical)

        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [self._orm_to_domain(row) for row in rows]
