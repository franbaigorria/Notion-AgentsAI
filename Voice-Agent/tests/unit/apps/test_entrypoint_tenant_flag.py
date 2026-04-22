"""Entrypoint tests for the thin-tenant MVP path.

When USE_TENANT_REGISTRY=false, the agent may still receive tenant_id metadata
from scripts/test_client.py, but it must not instantiate the vault or touch DB.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


SAMPLE_METADATA = json.dumps({"tenant_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"})


def _ctx_with_metadata() -> MagicMock:
    ctx = MagicMock()
    ctx.job.metadata = SAMPLE_METADATA
    ctx.room = MagicMock()
    ctx.connect = AsyncMock()
    return ctx


def _minimal_config() -> dict:
    return {
        "persona": "Sos un agente de prueba.",
        "greeting": "Hola.",
        "stt_provider": "deepgram",
        "stt_model": "nova-3",
        "llm_provider": "claude",
        "llm_model": "claude-haiku-4-5-20251001",
        "tts_provider": "elevenlabs",
        "tts_model": "eleven_flash_v2_5",
        "voice_id": "voice-id",
    }


def _session_mock() -> MagicMock:
    session = MagicMock()
    session.on = MagicMock()
    session.start = AsyncMock()
    session.generate_reply = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_pipeline_entrypoint_does_not_build_vault_when_registry_disabled(
    monkeypatch,
) -> None:
    from apps.pipeline import agent as pipeline_agent

    monkeypatch.setenv("USE_TENANT_REGISTRY", "false")
    monkeypatch.delenv("VAULT_MASTER_KEY", raising=False)

    ctx = _ctx_with_metadata()
    session = _session_mock()

    with (
        patch.object(pipeline_agent, "load_vertical", return_value=_minimal_config()),
        patch.object(pipeline_agent, "build_stt", AsyncMock(return_value="stt")) as build_stt,
        patch.object(pipeline_agent, "build_llm", AsyncMock(return_value="llm")) as build_llm,
        patch.object(pipeline_agent, "build_tts", AsyncMock(return_value="tts")) as build_tts,
        patch.object(pipeline_agent.silero.VAD, "load", return_value="vad"),
        patch.object(pipeline_agent, "AgentSession", return_value=session),
    ):
        await pipeline_agent.entrypoint(ctx)

    ctx.connect.assert_awaited_once()
    build_stt.assert_awaited_once()
    build_llm.assert_awaited_once()
    build_tts.assert_awaited_once()
    assert build_stt.await_args.kwargs["tenant_ctx"] is None
    assert build_llm.await_args.kwargs["tenant_ctx"] is None
    assert build_tts.await_args.kwargs["tenant_ctx"] is None


@pytest.mark.asyncio
async def test_realtime_entrypoint_does_not_build_vault_when_registry_disabled(
    monkeypatch,
) -> None:
    from apps.realtime import agent as realtime_agent

    monkeypatch.setenv("USE_TENANT_REGISTRY", "false")
    monkeypatch.delenv("VAULT_MASTER_KEY", raising=False)

    ctx = _ctx_with_metadata()
    session = _session_mock()

    with (
        patch.object(realtime_agent, "load_vertical", return_value=_minimal_config()),
        patch.object(
            realtime_agent,
            "build_realtime_llm",
            AsyncMock(return_value="realtime-llm"),
        ) as build_realtime_llm,
        patch.object(realtime_agent, "AgentSession", return_value=session),
    ):
        await realtime_agent.entrypoint(ctx)

    ctx.connect.assert_awaited_once()
    build_realtime_llm.assert_awaited_once()
    assert build_realtime_llm.await_args.kwargs["tenant_ctx"] is None
