"""Tests para TenantRegistry ABC — contrato de interfaz y tipos.

Task 2.1 (RED): Verifica que existan TenantRegistry, Tenant, TenantId,
TenantNotFound y TenantDisabled. Espera ImportError hasta que
core/tenants/base.py exista (Task 2.2 GREEN).
"""

import inspect
from dataclasses import fields
from uuid import UUID

import pytest


# ---------------------------------------------------------------------------
# Imports — must all resolve after Task 2.2 (GREEN)
# ---------------------------------------------------------------------------

from core.tenants.base import (
    Tenant,
    TenantDisabled,
    TenantId,
    TenantNotFound,
    TenantRegistry,
)


# ---------------------------------------------------------------------------
# TenantId
# ---------------------------------------------------------------------------


def test_tenant_id_is_newtype_of_uuid():
    """TenantId debe ser un NewType sobre UUID."""
    raw = UUID("12345678-1234-5678-1234-567812345678")
    tid = TenantId(raw)
    assert tid == raw


# ---------------------------------------------------------------------------
# Tenant dataclass
# ---------------------------------------------------------------------------


def test_tenant_dataclass_has_required_fields():
    """Tenant debe tener id, name, vertical, config, status, created_at, updated_at."""
    field_names = {f.name for f in fields(Tenant)}
    required = {"id", "name", "vertical", "config", "status", "created_at", "updated_at"}
    missing = required - field_names
    assert not missing, f"Tenant le faltan campos: {missing}"


def test_tenant_defaults():
    """config debe defaultear a {}, status a 'active', timestamps a None."""
    tid = TenantId(UUID("12345678-1234-5678-1234-567812345678"))
    tenant = Tenant(id=tid, name="Clínica del Valle", vertical="dental")
    assert tenant.config == {}
    assert tenant.status == "active"
    assert tenant.created_at is None
    assert tenant.updated_at is None


def test_tenant_status_can_be_disabled():
    tid = TenantId(UUID("12345678-1234-5678-1234-567812345678"))
    tenant = Tenant(id=tid, name="Demo", vertical="legal", status="disabled")
    assert tenant.status == "disabled"


# ---------------------------------------------------------------------------
# Exception types
# ---------------------------------------------------------------------------


def test_tenant_not_found_is_exception():
    assert issubclass(TenantNotFound, Exception)


def test_tenant_disabled_is_exception():
    assert issubclass(TenantDisabled, Exception)


def test_tenant_not_found_can_be_raised_and_caught():
    with pytest.raises(TenantNotFound):
        raise TenantNotFound("tenant 123 not found")


def test_tenant_disabled_can_be_raised_and_caught():
    with pytest.raises(TenantDisabled):
        raise TenantDisabled("tenant 123 is disabled")


# ---------------------------------------------------------------------------
# TenantRegistry ABC — method signatures
# ---------------------------------------------------------------------------


def test_tenant_registry_is_abstract():
    """No debe poder instanciarse directamente."""
    with pytest.raises(TypeError):
        TenantRegistry()  # type: ignore[abstract]


def test_registry_has_get_method():
    sig = inspect.signature(TenantRegistry.get)
    assert "tenant_id" in sig.parameters


def test_registry_has_create_method():
    sig = inspect.signature(TenantRegistry.create)
    assert "tenant" in sig.parameters


def test_registry_has_update_method():
    sig = inspect.signature(TenantRegistry.update)
    assert "tenant_id" in sig.parameters
    assert "patch" in sig.parameters


def test_registry_has_disable_method():
    sig = inspect.signature(TenantRegistry.disable)
    assert "tenant_id" in sig.parameters


def test_registry_has_list_method():
    sig = inspect.signature(TenantRegistry.list)
    assert "vertical" in sig.parameters


def test_all_abstract_methods_present():
    """Todos los métodos abstractos exigidos deben estar en la ABC."""
    abstract_methods = TenantRegistry.__abstractmethods__
    expected = {"get", "create", "update", "disable", "list"}
    missing = expected - abstract_methods
    assert not missing, f"Métodos abstractos faltantes: {missing}"
