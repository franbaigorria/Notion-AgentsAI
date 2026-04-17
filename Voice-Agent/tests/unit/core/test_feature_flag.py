"""Tests para feature flag USE_TENANT_REGISTRY y extracción de tenant_id.

Task 4.6 (RED → GREEN): Verifica que:
- _tenant_registry_enabled() retorna True solo con "true" exacto
- _extract_tenant_id_from_job() parsea correctamente el JSON de job.metadata
- Valores inválidos se manejan con gracia (retorna None, no excepciones)
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import UUID



# ---------------------------------------------------------------------------
# Imports bajo test
# ---------------------------------------------------------------------------

from core.orchestrator.agent import _tenant_registry_enabled
from apps.pipeline.agent import _extract_tenant_id_from_job as pipeline_extract
from apps.realtime.agent import _extract_tenant_id_from_job as realtime_extract


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_ctx(metadata: str = "") -> MagicMock:
    """Mock de JobContext con job.metadata configurable."""
    ctx = MagicMock()
    ctx.job.metadata = metadata
    return ctx


SAMPLE_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


# ---------------------------------------------------------------------------
# _tenant_registry_enabled() — feature flag
# ---------------------------------------------------------------------------


def test_flag_enabled_with_true(monkeypatch):
    """Solo 'true' activa el flag."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "true")
    assert _tenant_registry_enabled() is True


def test_flag_disabled_when_unset(monkeypatch):
    """Sin la variable, el flag está OFF."""
    monkeypatch.delenv("USE_TENANT_REGISTRY", raising=False)
    assert _tenant_registry_enabled() is False


def test_flag_disabled_with_false(monkeypatch):
    """'false' → OFF."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "false")
    assert _tenant_registry_enabled() is False


def test_flag_disabled_with_True_uppercase(monkeypatch):
    """'True' (mayúscula) → OFF (case-sensitive)."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "True")
    assert _tenant_registry_enabled() is False


def test_flag_disabled_with_1(monkeypatch):
    """'1' → OFF (solo 'true' exacto funciona)."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "1")
    assert _tenant_registry_enabled() is False


def test_flag_disabled_with_yes(monkeypatch):
    """'yes' → OFF."""
    monkeypatch.setenv("USE_TENANT_REGISTRY", "yes")
    assert _tenant_registry_enabled() is False


# ---------------------------------------------------------------------------
# _extract_tenant_id_from_job() — pipeline version
# ---------------------------------------------------------------------------


def test_pipeline_extract_valid_json():
    """Parsea correctamente JSON con tenant_id."""
    metadata = json.dumps({"tenant_id": SAMPLE_UUID})
    ctx = make_ctx(metadata)

    result = pipeline_extract(ctx)

    assert result is not None
    assert isinstance(result, UUID)
    assert str(result) == SAMPLE_UUID


def test_pipeline_extract_empty_metadata():
    """metadata vacío → None."""
    ctx = make_ctx("")
    result = pipeline_extract(ctx)
    assert result is None


def test_pipeline_extract_invalid_json():
    """metadata no-JSON → None (no exception)."""
    ctx = make_ctx("not-json-at-all")
    result = pipeline_extract(ctx)
    assert result is None


def test_pipeline_extract_json_without_tenant_id():
    """JSON válido pero sin clave tenant_id → None."""
    ctx = make_ctx(json.dumps({"other_key": "value"}))
    result = pipeline_extract(ctx)
    assert result is None


def test_pipeline_extract_invalid_uuid_in_metadata():
    """tenant_id presente pero UUID inválido → None."""
    ctx = make_ctx(json.dumps({"tenant_id": "not-a-uuid"}))
    result = pipeline_extract(ctx)
    assert result is None


def test_pipeline_extract_extra_fields_ok():
    """JSON con campos adicionales — solo se usa tenant_id."""
    metadata = json.dumps({"tenant_id": SAMPLE_UUID, "region": "us-east", "version": 2})
    ctx = make_ctx(metadata)

    result = pipeline_extract(ctx)

    assert result is not None
    assert str(result) == SAMPLE_UUID


# ---------------------------------------------------------------------------
# _extract_tenant_id_from_job() — realtime version (misma lógica)
# ---------------------------------------------------------------------------


def test_realtime_extract_valid_json():
    """Realtime: parsea correctamente JSON con tenant_id."""
    metadata = json.dumps({"tenant_id": SAMPLE_UUID})
    ctx = make_ctx(metadata)

    result = realtime_extract(ctx)

    assert result is not None
    assert str(result) == SAMPLE_UUID


def test_realtime_extract_empty_metadata():
    """Realtime: metadata vacío → None."""
    ctx = make_ctx("")
    result = realtime_extract(ctx)
    assert result is None


def test_realtime_extract_invalid_json():
    """Realtime: metadata no-JSON → None."""
    ctx = make_ctx("garbage")
    result = realtime_extract(ctx)
    assert result is None
