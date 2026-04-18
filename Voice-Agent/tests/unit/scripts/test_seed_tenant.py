"""Unit tests — scripts/seed_tenant.py (Phase 2.1 RED).

Covers:
  - argparse: required flags, optional --tenant-id, repeatable --secret KEY=VALUE
  - argparse: malformed --secret raises argparse.ArgumentTypeError
  - env fast-fail: missing DATABASE_URL or VAULT_MASTER_KEY exits non-zero BEFORE any DB access
  - seed: creates a new tenant + stores all secrets when no --tenant-id is given
  - seed: idempotent upsert path — existing tenant_id triggers update(), not create()
  - seed: when --tenant-id is given but tenant does not exist, creates with that id

All tests mock the registry + vault adapters — no Postgres dependency.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from core.tenants.base import Tenant, TenantId, TenantNotFound
from scripts.seed_tenant import _parse_args, _parse_secret_arg, _require_env, seed_tenant


# ---------------------------------------------------------------------------
# _require_env
# ---------------------------------------------------------------------------


def test_require_env_returns_value_when_set() -> None:
    with patch.dict(os.environ, {"SEED_TEST_VAR": "hello"}):
        assert _require_env("SEED_TEST_VAR") == "hello"


def test_require_env_exits_when_missing() -> None:
    env_without_key = {k: v for k, v in os.environ.items() if k != "SEED_MISSING_XYZ"}
    with patch.dict(os.environ, env_without_key, clear=True):
        with pytest.raises(SystemExit) as exc_info:
            _require_env("SEED_MISSING_XYZ")
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# _parse_secret_arg
# ---------------------------------------------------------------------------


def test_parse_secret_arg_valid() -> None:
    assert _parse_secret_arg("deepgram=abc123") == ("deepgram", "abc123")


def test_parse_secret_arg_value_may_contain_equals() -> None:
    assert _parse_secret_arg("token=a=b=c") == ("token", "a=b=c")


def test_parse_secret_arg_rejects_missing_equals() -> None:
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        _parse_secret_arg("no-equals-here")


def test_parse_secret_arg_rejects_empty_key() -> None:
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        _parse_secret_arg("=value")


def test_parse_secret_arg_rejects_empty_value() -> None:
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        _parse_secret_arg("key=")


# ---------------------------------------------------------------------------
# _parse_args
# ---------------------------------------------------------------------------


def test_parse_args_minimal() -> None:
    ns = _parse_args(["--name", "Demo", "--vertical", "clinica"])
    assert ns.name == "Demo"
    assert ns.vertical == "clinica"
    assert ns.tenant_id is None
    assert ns.secret == []


def test_parse_args_with_tenant_id_and_secrets() -> None:
    tid = uuid.uuid4()
    ns = _parse_args(
        [
            "--name",
            "Clinica Demo",
            "--vertical",
            "clinica",
            "--tenant-id",
            str(tid),
            "--secret",
            "deepgram=dg-key",
            "--secret",
            "claude=cl-key",
            "--secret",
            "elevenlabs=el-key",
        ]
    )
    assert ns.tenant_id == tid
    assert ns.secret == [
        ("deepgram", "dg-key"),
        ("claude", "cl-key"),
        ("elevenlabs", "el-key"),
    ]


def test_parse_args_missing_required_exits() -> None:
    with pytest.raises(SystemExit):
        _parse_args(["--name", "Demo"])  # missing --vertical


# ---------------------------------------------------------------------------
# seed_tenant — core logic (mocked registry + vault)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_creates_new_tenant_when_no_id_given() -> None:
    """No --tenant-id → new UUID + registry.create() is called, not update()."""
    fake_tenant = Tenant(
        id=TenantId(uuid.uuid4()),
        name="Demo",
        vertical="clinica",
    )
    mock_registry = AsyncMock()
    mock_registry.create = AsyncMock(return_value=fake_tenant)
    mock_registry.update = AsyncMock()

    mock_vault = AsyncMock()
    mock_vault.store = AsyncMock()

    with (
        patch("scripts.seed_tenant._open_registry") as mock_open_reg,
        patch("scripts.seed_tenant._open_vault", return_value=mock_vault),
    ):
        mock_open_reg.return_value.__aenter__.return_value = mock_registry
        mock_open_reg.return_value.__aexit__.return_value = False

        result_id = await seed_tenant(
            name="Demo",
            vertical="clinica",
            tenant_id=None,
            secrets=[("deepgram", "dg-key"), ("claude", "cl-key")],
        )

    mock_registry.create.assert_awaited_once()
    mock_registry.update.assert_not_awaited()
    assert mock_vault.store.await_count == 2
    assert result_id == fake_tenant.id


@pytest.mark.asyncio
async def test_seed_updates_existing_tenant_idempotent() -> None:
    """--tenant-id that already exists → registry.update() is called, create() is NOT."""
    tid = uuid.uuid4()
    fake_updated = Tenant(
        id=TenantId(tid),
        name="Demo",
        vertical="clinica",
    )
    mock_registry = AsyncMock()
    mock_registry.update = AsyncMock(return_value=fake_updated)
    mock_registry.create = AsyncMock()

    mock_vault = AsyncMock()
    mock_vault.store = AsyncMock()

    with (
        patch("scripts.seed_tenant._open_registry") as mock_open_reg,
        patch("scripts.seed_tenant._open_vault", return_value=mock_vault),
    ):
        mock_open_reg.return_value.__aenter__.return_value = mock_registry
        mock_open_reg.return_value.__aexit__.return_value = False

        result_id = await seed_tenant(
            name="Demo",
            vertical="clinica",
            tenant_id=tid,
            secrets=[("deepgram", "dg-key-v2")],
        )

    mock_registry.update.assert_awaited_once()
    mock_registry.create.assert_not_awaited()
    mock_vault.store.assert_awaited_once()
    assert result_id == TenantId(tid)


@pytest.mark.asyncio
async def test_seed_creates_with_given_id_when_tenant_not_found() -> None:
    """--tenant-id that does NOT exist → update raises TenantNotFound, falls back to create()."""
    tid = uuid.uuid4()
    fake_created = Tenant(id=TenantId(tid), name="Demo", vertical="clinica")

    mock_registry = AsyncMock()
    mock_registry.update = AsyncMock(side_effect=TenantNotFound(f"Tenant {tid} not found"))
    mock_registry.create = AsyncMock(return_value=fake_created)

    mock_vault = AsyncMock()
    mock_vault.store = AsyncMock()

    with (
        patch("scripts.seed_tenant._open_registry") as mock_open_reg,
        patch("scripts.seed_tenant._open_vault", return_value=mock_vault),
    ):
        mock_open_reg.return_value.__aenter__.return_value = mock_registry
        mock_open_reg.return_value.__aexit__.return_value = False

        result_id = await seed_tenant(
            name="Demo",
            vertical="clinica",
            tenant_id=tid,
            secrets=[],
        )

    mock_registry.update.assert_awaited_once()
    mock_registry.create.assert_awaited_once()
    mock_vault.store.assert_not_awaited()
    assert result_id == TenantId(tid)


@pytest.mark.asyncio
async def test_seed_with_zero_secrets_does_not_call_vault() -> None:
    """Empty --secret list → vault.store is never called."""
    fake_tenant = Tenant(id=TenantId(uuid.uuid4()), name="Demo", vertical="clinica")
    mock_registry = AsyncMock()
    mock_registry.create = AsyncMock(return_value=fake_tenant)

    mock_vault = AsyncMock()

    with (
        patch("scripts.seed_tenant._open_registry") as mock_open_reg,
        patch("scripts.seed_tenant._open_vault", return_value=mock_vault),
    ):
        mock_open_reg.return_value.__aenter__.return_value = mock_registry
        mock_open_reg.return_value.__aexit__.return_value = False

        await seed_tenant(
            name="Demo",
            vertical="clinica",
            tenant_id=None,
            secrets=[],
        )

    mock_vault.store.assert_not_awaited()
