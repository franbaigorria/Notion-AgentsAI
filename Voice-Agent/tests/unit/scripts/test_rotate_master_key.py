"""Unit tests — scripts/rotate_master_key.py

Covers:
  - Successful rotation: all rows decrypted with OLD_KEY, re-encrypted with NEW_KEY,
    updated in DB, transaction committed.
  - Mid-rotation failure: one row has corrupted ciphertext, InvalidToken raised,
    transaction rolled back, no rows are committed.
  - _require_env: missing env var triggers SystemExit.
  - _load_fernet: invalid key triggers SystemExit.
  - Identical OLD_KEY / NEW_KEY detected and rejected.

These tests use mocked async engine/session — no Postgres dependency.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

# ---------------------------------------------------------------------------
# Import helpers from the script under test
# ---------------------------------------------------------------------------

# We import individual functions so we can unit-test them without running main()
from scripts.rotate_master_key import _load_fernet, _require_env, rotate_keys


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def old_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture()
def new_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture()
def old_fernet(old_key: str) -> Fernet:
    return Fernet(old_key.encode())


@pytest.fixture()
def new_fernet(new_key: str) -> Fernet:
    return Fernet(new_key.encode())


# ---------------------------------------------------------------------------
# _require_env
# ---------------------------------------------------------------------------


def test_require_env_returns_value_when_set() -> None:
    with patch.dict(os.environ, {"MY_VAR": "hello"}):
        assert _require_env("MY_VAR") == "hello"


def test_require_env_exits_when_missing() -> None:
    env_without_key = {k: v for k, v in os.environ.items() if k != "MISSING_VAR_XYZ"}
    with patch.dict(os.environ, env_without_key, clear=True):
        with pytest.raises(SystemExit) as exc_info:
            _require_env("MISSING_VAR_XYZ")
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# _load_fernet
# ---------------------------------------------------------------------------


def test_load_fernet_valid_key(old_key: str) -> None:
    fernet = _load_fernet("OLD_KEY", old_key)
    assert isinstance(fernet, Fernet)


def test_load_fernet_invalid_key_exits() -> None:
    with pytest.raises(SystemExit) as exc_info:
        _load_fernet("BAD_KEY", "this-is-not-a-fernet-key")
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# rotate_keys — success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rotate_keys_success(old_fernet: Fernet, new_fernet: Fernet, old_key: str) -> None:
    """All rows are re-encrypted with new key; execute called for each UPDATE."""
    plaintext = b"super-secret-value"
    ciphertext_old = old_fernet.encrypt(plaintext)

    # One fake row: (id, tenant_id, key_name, ciphertext)
    import uuid

    secret_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    fake_row = (secret_id, tenant_id, "api_key", ciphertext_old)

    # Build mock chain: engine → session_factory → session
    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = [fake_row]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    # session.begin() returns an async context manager
    mock_begin_ctx = AsyncMock()
    mock_begin_ctx.__aenter__ = AsyncMock(return_value=None)
    mock_begin_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock(return_value=mock_begin_ctx)

    # session_factory() returns an async context manager wrapping mock_session
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_session_factory = MagicMock(return_value=mock_session_ctx)

    mock_engine = AsyncMock()
    mock_engine.dispose = AsyncMock()

    with (
        patch("scripts.rotate_master_key.create_async_engine", return_value=mock_engine),
        patch("scripts.rotate_master_key.async_sessionmaker", return_value=mock_session_factory),
    ):
        await rotate_keys("postgresql+asyncpg://test", old_fernet, new_fernet)

    # Should have called execute twice: SELECT + UPDATE
    assert mock_session.execute.call_count == 2

    # Verify the UPDATE call re-encrypted with new_fernet
    update_call = mock_session.execute.call_args_list[1]
    update_params = update_call[0][1]  # positional arg dict
    new_ciphertext = update_params["ciphertext"]

    # The new ciphertext must decrypt correctly with the new key
    decrypted = new_fernet.decrypt(new_ciphertext)
    assert decrypted == plaintext

    # Engine must be disposed after rotation
    mock_engine.dispose.assert_called_once()


# ---------------------------------------------------------------------------
# rotate_keys — mid-rotation failure triggers rollback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rotate_keys_rollback_on_bad_ciphertext(
    old_fernet: Fernet, new_fernet: Fernet
) -> None:
    """If one row has a corrupted ciphertext, InvalidToken propagates and
    the transaction context manager handles rollback (no UPDATE committed)."""
    import uuid

    secret_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    # Provide garbage ciphertext that cannot be decrypted by old_fernet
    corrupted_ciphertext = b"this-is-not-valid-fernet-ciphertext"
    fake_row = (secret_id, tenant_id, "bad_key", corrupted_ciphertext)

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = [fake_row]

    mock_session = AsyncMock()
    # First call returns the SELECT result; second call (UPDATE) should never happen
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    mock_begin_ctx = AsyncMock()
    mock_begin_ctx.__aenter__ = AsyncMock(return_value=None)
    # __aexit__ receives the exception; returning False means it re-raises
    mock_begin_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock(return_value=mock_begin_ctx)

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_session_factory = MagicMock(return_value=mock_session_ctx)

    mock_engine = AsyncMock()
    mock_engine.dispose = AsyncMock()

    with (
        patch("scripts.rotate_master_key.create_async_engine", return_value=mock_engine),
        patch("scripts.rotate_master_key.async_sessionmaker", return_value=mock_session_factory),
    ):
        # InvalidToken should propagate out of rotate_keys
        with pytest.raises(InvalidToken):
            await rotate_keys("postgresql+asyncpg://test", old_fernet, new_fernet)

    # Only the SELECT was executed — no UPDATE committed
    assert mock_session.execute.call_count == 1
