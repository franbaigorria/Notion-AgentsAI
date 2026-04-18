"""Unit tests — builders threading TenantContext for vault-resolved api keys (Phase 3.1 RED).

Verifies the multi-tenant wiring:
  - build_stt / build_llm / build_tts / build_realtime_llm are `async def`
  - accept `tenant_ctx: TenantContext | None = None` keyword-only
  - when ctx present, call `ctx.get_secret(<vault_key>)` once and pass to adapter
  - when ctx None, NO vault call; adapter is constructed with api_key=None

Patches the adapter classes to inspect the kwargs — avoids spinning up real
LiveKit plugins.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("ENV", "test")


# ---------------------------------------------------------------------------
# build_stt
# ---------------------------------------------------------------------------


class TestBuildSTTWithTenantCtx:
    @pytest.mark.asyncio
    async def test_with_tenant_ctx_passes_api_key_to_adapter(self) -> None:
        from core.orchestrator import agent as orch_agent

        mock_ctx = AsyncMock()
        mock_ctx.get_secret = AsyncMock(return_value="dg-from-vault")

        with patch.object(orch_agent, "DeepgramSTT", create=True) as MockDeepgram:
            instance = MagicMock()
            instance.as_livekit_plugin.return_value = "plugin-obj"
            MockDeepgram.return_value = instance

            # Re-import the submodule symbol inside build_stt via patching the actual module path
            with patch("core.stt.deepgram.DeepgramSTT", MockDeepgram):
                result = await orch_agent.build_stt(
                    {"stt_provider": "deepgram"}, tenant_ctx=mock_ctx
                )

        mock_ctx.get_secret.assert_awaited_once_with("deepgram")
        # The adapter was constructed with api_key from the vault
        kwargs = MockDeepgram.call_args.kwargs
        assert kwargs.get("api_key") == "dg-from-vault"
        assert result == "plugin-obj"

    @pytest.mark.asyncio
    async def test_without_tenant_ctx_passes_none_and_no_vault_call(self) -> None:
        from core.orchestrator import agent as orch_agent

        with patch("core.stt.deepgram.DeepgramSTT") as MockDeepgram:
            instance = MagicMock()
            instance.as_livekit_plugin.return_value = "plugin-obj"
            MockDeepgram.return_value = instance

            await orch_agent.build_stt({"stt_provider": "deepgram"})

        kwargs = MockDeepgram.call_args.kwargs
        assert kwargs.get("api_key") is None


# ---------------------------------------------------------------------------
# build_llm
# ---------------------------------------------------------------------------


class TestBuildLLMWithTenantCtx:
    @pytest.mark.asyncio
    async def test_claude_with_tenant_ctx_resolves_claude_key(self) -> None:
        from core.orchestrator import agent as orch_agent

        mock_ctx = AsyncMock()
        mock_ctx.get_secret = AsyncMock(return_value="cl-from-vault")

        with patch("core.llm.claude.ClaudeLLM") as MockClaude:
            instance = MagicMock()
            instance.as_livekit_plugin.return_value = "claude-plugin"
            MockClaude.return_value = instance

            await orch_agent.build_llm({"llm_provider": "claude"}, tenant_ctx=mock_ctx)

        mock_ctx.get_secret.assert_awaited_once_with("claude")
        assert MockClaude.call_args.kwargs.get("api_key") == "cl-from-vault"

    @pytest.mark.asyncio
    async def test_gemini_resolves_under_google_vault_key(self) -> None:
        """Unified vault key — gemini provider → 'google' vault entry."""
        from core.orchestrator import agent as orch_agent

        mock_ctx = AsyncMock()
        mock_ctx.get_secret = AsyncMock(return_value="google-from-vault")

        with patch("core.llm.gemini.GeminiLLM") as MockGemini:
            instance = MagicMock()
            instance.as_livekit_plugin.return_value = "gemini-plugin"
            MockGemini.return_value = instance

            await orch_agent.build_llm({"llm_provider": "gemini"}, tenant_ctx=mock_ctx)

        mock_ctx.get_secret.assert_awaited_once_with("google")
        assert MockGemini.call_args.kwargs.get("api_key") == "google-from-vault"

    @pytest.mark.asyncio
    async def test_ollama_with_tenant_ctx_does_not_call_vault(self) -> None:
        """Ollama is local — sentinel empty string in the dict skips the vault."""
        from core.orchestrator import agent as orch_agent

        mock_ctx = AsyncMock()
        mock_ctx.get_secret = AsyncMock()

        with patch("core.llm.ollama.OllamaLLM") as MockOllama:
            instance = MagicMock()
            instance.as_livekit_plugin.return_value = "ollama-plugin"
            MockOllama.return_value = instance

            await orch_agent.build_llm({"llm_provider": "ollama"}, tenant_ctx=mock_ctx)

        mock_ctx.get_secret.assert_not_awaited()


# ---------------------------------------------------------------------------
# build_tts
# ---------------------------------------------------------------------------


class TestBuildTTSWithTenantCtx:
    @pytest.mark.asyncio
    async def test_elevenlabs_with_tenant_ctx_passes_api_key(self) -> None:
        from core.orchestrator import agent as orch_agent

        mock_ctx = AsyncMock()
        mock_ctx.get_secret = AsyncMock(return_value="el-from-vault")

        with patch("core.tts.elevenlabs.ElevenLabsTTS") as MockEL:
            instance = MagicMock()
            instance.as_livekit_plugin.return_value = "el-plugin"
            MockEL.return_value = instance

            await orch_agent.build_tts(
                {"tts_provider": "elevenlabs", "voice_id": "vid"},
                tenant_ctx=mock_ctx,
            )

        mock_ctx.get_secret.assert_awaited_once_with("elevenlabs")
        assert MockEL.call_args.kwargs.get("api_key") == "el-from-vault"

    @pytest.mark.asyncio
    async def test_without_tenant_ctx_passes_none(self) -> None:
        from core.orchestrator import agent as orch_agent

        with patch("core.tts.deepgram.DeepgramTTS") as MockDG:
            instance = MagicMock()
            instance.as_livekit_plugin.return_value = "dg-plugin"
            MockDG.return_value = instance

            await orch_agent.build_tts({"tts_provider": "deepgram"})

        assert MockDG.call_args.kwargs.get("api_key") is None


# ---------------------------------------------------------------------------
# build_realtime_llm
# ---------------------------------------------------------------------------


class TestBuildRealtimeLLMWithTenantCtx:
    @pytest.mark.asyncio
    async def test_with_tenant_ctx_resolves_openai_key(self) -> None:
        from core.orchestrator import agent as orch_agent

        mock_ctx = AsyncMock()
        mock_ctx.get_secret = AsyncMock(return_value="oa-rt-from-vault")

        with patch("core.llm.openai_realtime.OpenAIRealtime") as MockRT:
            instance = MagicMock()
            instance.as_livekit_plugin.return_value = "rt-plugin"
            MockRT.return_value = instance

            await orch_agent.build_realtime_llm({}, tenant_ctx=mock_ctx)

        mock_ctx.get_secret.assert_awaited_once_with("openai")
        assert MockRT.call_args.kwargs.get("api_key") == "oa-rt-from-vault"

    @pytest.mark.asyncio
    async def test_without_tenant_ctx_passes_none(self) -> None:
        from core.orchestrator import agent as orch_agent

        with patch("core.llm.openai_realtime.OpenAIRealtime") as MockRT:
            instance = MagicMock()
            instance.as_livekit_plugin.return_value = "rt-plugin"
            MockRT.return_value = instance

            await orch_agent.build_realtime_llm({})

        assert MockRT.call_args.kwargs.get("api_key") is None
