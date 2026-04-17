"""core.tenants — Tenant Registry domain package.

Public API::

    from core.tenants.base import Tenant, TenantId, TenantRegistry
    from core.tenants.base import TenantNotFound, TenantDisabled
    from core.tenants.postgres import PostgresTenantRegistry
"""

from core.tenants.base import (
    Tenant,
    TenantDisabled,
    TenantId,
    TenantNotFound,
    TenantRegistry,
)

__all__ = [
    "Tenant",
    "TenantDisabled",
    "TenantId",
    "TenantNotFound",
    "TenantRegistry",
]
