"""Unit tests — scripts/test_client.py (Phase 3.1 RED).

Covers:
  - argparse: --tenant-id required, optional --room / --agent-name / --timeout
  - env fast-fail: missing LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET exits 1
  - dispatch metadata: tenant_id is encoded as JSON in CreateAgentDispatchRequest.metadata
  - dispatch call shape: LiveKitAPI.agent_dispatch.create_dispatch is awaited with the right args
  - participant token generation: AccessToken.with_grants + with_identity round-trip

No LiveKit server required — the LiveKitAPI client is mocked.
"""

from __future__ import annotations

import json
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.test_client import (
    _build_dispatch_request,
    _generate_participant_token,
    _parse_args,
    _require_env,
    dispatch_and_wait,
)


# ---------------------------------------------------------------------------
# _require_env
# ---------------------------------------------------------------------------


def test_require_env_returns_value_when_set() -> None:
    with patch.dict(os.environ, {"TC_TEST_VAR": "ok"}):
        assert _require_env("TC_TEST_VAR") == "ok"


def test_require_env_exits_when_missing() -> None:
    env_without = {k: v for k, v in os.environ.items() if k != "TC_MISSING_XYZ"}
    with patch.dict(os.environ, env_without, clear=True):
        with pytest.raises(SystemExit) as exc_info:
            _require_env("TC_MISSING_XYZ")
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# _parse_args
# ---------------------------------------------------------------------------


def test_parse_args_minimal() -> None:
    tid = uuid.uuid4()
    ns = _parse_args(["--tenant-id", str(tid)])
    assert ns.tenant_id == tid
    # Defaults
    assert ns.room is None  # auto-generated at runtime
    assert ns.agent_name == "pipeline-agent"
    assert ns.timeout == 60


def test_parse_args_all_flags() -> None:
    tid = uuid.uuid4()
    ns = _parse_args(
        [
            "--tenant-id",
            str(tid),
            "--room",
            "test-room-42",
            "--agent-name",
            "realtime-agent",
            "--timeout",
            "120",
        ]
    )
    assert ns.tenant_id == tid
    assert ns.room == "test-room-42"
    assert ns.agent_name == "realtime-agent"
    assert ns.timeout == 120


def test_parse_args_missing_tenant_id_exits() -> None:
    with pytest.raises(SystemExit):
        _parse_args([])


# ---------------------------------------------------------------------------
# _build_dispatch_request — metadata JSON contract
# ---------------------------------------------------------------------------


def test_build_dispatch_request_encodes_tenant_id_as_json() -> None:
    tid = uuid.uuid4()
    req = _build_dispatch_request(tenant_id=tid, room="r1", agent_name="pipeline-agent")
    assert req.agent_name == "pipeline-agent"
    assert req.room == "r1"
    # metadata is a JSON string — the agent parses it in _extract_tenant_id_from_job
    parsed = json.loads(req.metadata)
    assert parsed == {"tenant_id": str(tid)}


def test_build_dispatch_request_with_different_agent_name() -> None:
    tid = uuid.uuid4()
    req = _build_dispatch_request(
        tenant_id=tid, room="r2", agent_name="realtime-agent"
    )
    assert req.agent_name == "realtime-agent"


# ---------------------------------------------------------------------------
# _generate_participant_token
# ---------------------------------------------------------------------------


def test_generate_participant_token_returns_non_empty_string() -> None:
    token = _generate_participant_token(
        api_key="devkey",
        api_secret="devsecret" * 4,  # ≥ 32 chars for JWT signing
        room="r1",
        identity="operator",
    )
    assert isinstance(token, str)
    # JWTs are dot-separated three-part strings
    assert token.count(".") == 2


# ---------------------------------------------------------------------------
# dispatch_and_wait — invokes LiveKitAPI correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_and_wait_calls_create_dispatch() -> None:
    """dispatch_and_wait opens LiveKitAPI, calls create_dispatch with the right request,
    polls participants, and closes the session."""
    tid = uuid.uuid4()

    # Mock dispatch response
    fake_dispatch = MagicMock()
    fake_dispatch.id = "disp-123"

    # Mock participant list — agent detected on second poll
    fake_participant_agent = MagicMock()
    fake_participant_agent.identity = "agent-abc"
    fake_participant_agent.kind = 2  # AGENT kind (livekit enum)
    fake_participant_agent.attributes = {"lk.agent.name": "pipeline-agent"}

    empty_response = MagicMock()
    empty_response.participants = []
    agent_response = MagicMock()
    agent_response.participants = [fake_participant_agent]

    mock_dispatch_service = MagicMock()
    mock_dispatch_service.create_dispatch = AsyncMock(return_value=fake_dispatch)

    mock_room_service = MagicMock()
    mock_room_service.list_participants = AsyncMock(
        side_effect=[empty_response, agent_response]
    )

    mock_lkapi = MagicMock()
    mock_lkapi.agent_dispatch = mock_dispatch_service
    mock_lkapi.room = mock_room_service
    mock_lkapi.aclose = AsyncMock()

    with patch("scripts.test_client.LiveKitAPI", return_value=mock_lkapi):
        result = await dispatch_and_wait(
            livekit_url="wss://fake",
            api_key="k",
            api_secret="s" * 32,
            tenant_id=tid,
            room="r1",
            agent_name="pipeline-agent",
            timeout_seconds=5,
            poll_interval=0.01,
        )

    mock_dispatch_service.create_dispatch.assert_awaited_once()
    called_req = mock_dispatch_service.create_dispatch.await_args.args[0]
    assert called_req.agent_name == "pipeline-agent"
    assert called_req.room == "r1"
    assert json.loads(called_req.metadata) == {"tenant_id": str(tid)}

    assert result["dispatch_id"] == "disp-123"
    assert result["agent_identity"] == "agent-abc"

    mock_lkapi.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_and_wait_ignores_agent_with_wrong_name() -> None:
    """Explicit dispatch must wait for the requested named worker, not any agent."""
    tid = uuid.uuid4()
    fake_dispatch = MagicMock()
    fake_dispatch.id = "disp-123"

    wrong_agent = MagicMock()
    wrong_agent.identity = "wrong-agent"
    wrong_agent.kind = 2
    wrong_agent.attributes = {"lk.agent.name": "realtime-agent"}

    right_agent = MagicMock()
    right_agent.identity = "pipeline-agent-abc"
    right_agent.kind = 2
    right_agent.attributes = {"lk.agent.name": "pipeline-agent"}

    wrong_response = MagicMock()
    wrong_response.participants = [wrong_agent]
    right_response = MagicMock()
    right_response.participants = [wrong_agent, right_agent]

    mock_lkapi = MagicMock()
    mock_lkapi.agent_dispatch = MagicMock()
    mock_lkapi.agent_dispatch.create_dispatch = AsyncMock(return_value=fake_dispatch)
    mock_lkapi.room = MagicMock()
    mock_lkapi.room.list_participants = AsyncMock(
        side_effect=[wrong_response, right_response]
    )
    mock_lkapi.aclose = AsyncMock()

    with patch("scripts.test_client.LiveKitAPI", return_value=mock_lkapi):
        result = await dispatch_and_wait(
            livekit_url="wss://fake",
            api_key="k",
            api_secret="s" * 32,
            tenant_id=tid,
            room="r1",
            agent_name="pipeline-agent",
            timeout_seconds=5,
            poll_interval=0.01,
        )

    assert result["agent_identity"] == "pipeline-agent-abc"


@pytest.mark.asyncio
async def test_dispatch_and_wait_times_out_when_agent_never_joins() -> None:
    """If the agent never shows up in the room, the function raises TimeoutError."""
    tid = uuid.uuid4()
    fake_dispatch = MagicMock()
    fake_dispatch.id = "disp-timeout"
    empty_response = MagicMock()
    empty_response.participants = []

    mock_lkapi = MagicMock()
    mock_lkapi.agent_dispatch = MagicMock()
    mock_lkapi.agent_dispatch.create_dispatch = AsyncMock(return_value=fake_dispatch)
    mock_lkapi.room = MagicMock()
    mock_lkapi.room.list_participants = AsyncMock(return_value=empty_response)
    mock_lkapi.aclose = AsyncMock()

    with patch("scripts.test_client.LiveKitAPI", return_value=mock_lkapi):
        with pytest.raises(TimeoutError):
            await dispatch_and_wait(
                livekit_url="wss://fake",
                api_key="k",
                api_secret="s" * 32,
                tenant_id=tid,
                room="r1",
                agent_name="pipeline-agent",
                timeout_seconds=0.05,
                poll_interval=0.01,
            )

    mock_lkapi.aclose.assert_awaited_once()
