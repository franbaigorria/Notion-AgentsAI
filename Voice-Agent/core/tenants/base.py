"""core.tenants.base — TenantRegistry ABC, Tenant dataclass y tipos auxiliares.

Define la interfaz pública del módulo de tenants. Los adaptadores concretos
(p.ej. PostgresTenantRegistry) importan desde aquí y extienden TenantRegistry.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, NewType
from uuid import UUID

# ---------------------------------------------------------------------------
# Tipos de dominio
# ---------------------------------------------------------------------------

TenantId = NewType("TenantId", UUID)

TenantStatus = Literal["active", "disabled"]


# ---------------------------------------------------------------------------
# Dataclass de dominio
# ---------------------------------------------------------------------------


@dataclass
class Tenant:
    """Configuración y estado de un tenant.

    Campos:
        id: Identificador único (UUID).
        name: Nombre único legible por humanos.
        vertical: Vertical de negocio (e.g. "dental", "legal", "real_estate").
        config: Diccionario de configuración libre (JSONB en Postgres).
        status: Estado del tenant — "active" o "disabled".
        created_at: Timestamp de creación (None si aún no se persistió).
        updated_at: Timestamp de última modificación (None si aún no se persistió).
    """

    id: TenantId
    name: str
    vertical: str
    config: dict[str, Any] = field(default_factory=dict)
    status: TenantStatus = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Excepciones de dominio
# ---------------------------------------------------------------------------


class TenantNotFound(Exception):
    """Se lanza cuando se busca un tenant por ID y no existe en el registry."""


class TenantDisabled(Exception):
    """Se lanza cuando se intenta operar con un tenant cuyo status es 'disabled'."""


# ---------------------------------------------------------------------------
# ABC — puerto de salida (Hexagonal Architecture)
# ---------------------------------------------------------------------------


class TenantRegistry(ABC):
    """CRUD de tenants — fuente de verdad para el onboarding data-driven.

    Todos los métodos son async para no bloquear el event loop de LiveKit.
    Los adaptadores concretos implementan estos métodos contra el backend
    de persistencia elegido (Postgres, in-memory para tests, etc.).

    Convención de errores:
        - get() puede retornar None si el tenant no existe, ó lanzar TenantNotFound.
          El adaptador de Postgres lanza TenantNotFound; stubs pueden retornar None.
        - get() de un tenant disabled → lanza TenantDisabled.
        - update() / disable() de un tenant inexistente → lanza TenantNotFound.
    """

    @abstractmethod
    async def get(self, tenant_id: TenantId) -> Tenant | None:
        """Retorna el Tenant correspondiente al ID.

        Args:
            tenant_id: UUID del tenant.

        Returns:
            Tenant si existe y está activo.

        Raises:
            TenantNotFound: si el tenant_id no existe.
            TenantDisabled: si el tenant existe pero está disabled.
        """
        ...

    @abstractmethod
    async def create(self, tenant: Tenant) -> Tenant:
        """Persiste un nuevo tenant y retorna la entidad con timestamps.

        Args:
            tenant: Dataclass Tenant con los campos a persistir.

        Returns:
            Tenant con created_at y updated_at poblados.
        """
        ...

    @abstractmethod
    async def update(self, tenant_id: TenantId, patch: dict[str, Any]) -> Tenant:
        """Aplica un patch parcial al tenant y retorna la entidad actualizada.

        Solo los campos presentes en `patch` son modificados.
        updated_at se refresca automáticamente.

        Args:
            tenant_id: UUID del tenant a modificar.
            patch: Diccionario con los campos a actualizar (e.g. {"vertical": "legal"}).

        Returns:
            Tenant actualizado.

        Raises:
            TenantNotFound: si el tenant_id no existe.
        """
        ...

    @abstractmethod
    async def disable(self, tenant_id: TenantId) -> None:
        """Marca el tenant como disabled (soft-delete).

        No elimina la fila físicamente. Preserva el historial de auditoría
        y evita problemas de FK con tenant_secrets.

        Args:
            tenant_id: UUID del tenant a deshabilitar.

        Raises:
            TenantNotFound: si el tenant_id no existe.
        """
        ...

    @abstractmethod
    async def list(self, vertical: str | None = None) -> list[Tenant]:
        """Lista todos los tenants activos, opcionalmente filtrados por vertical.

        Args:
            vertical: Si se provee, filtra por ese valor de vertical.
                      Si es None, retorna todos los tenants activos.

        Returns:
            Lista de Tenant (solo status='active' por defecto).
        """
        ...
