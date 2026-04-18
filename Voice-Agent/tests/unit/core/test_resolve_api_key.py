"""Unit tests — _resolve_api_key + _PROVIDER_VAULT_KEYS (Phase 1.1 RED).

Pure function that resolves a provider name to its vault-stored API key.
Used by build_stt / build_llm / build_tts / build_realtime_llm when a
TenantContext is present, so Railway deploys can resolve per-tenant keys
from the vault instead of global env vars.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("ENV", "test")

from core.orchestrator.agent import _PROVIDER_VAULT_KEYS, _resolve_api_key


class TestProviderVaultKeys:
    """The dict must cover the 8 canonical provider keys + ollama sentinel."""

    def test_has_all_supported_providers(self) -> None:
        expected_providers = {
            "deepgram",
            "elevenlabs",
            "claude",
            "openai",
            "groq",
            "cartesia",
            "gemini",
            "fish_speech",
            "ollama",
        }
        assert set(_PROVIDER_VAULT_KEYS.keys()) == expected_providers

    def test_gemini_maps_to_google_key(self) -> None:
        """Unified Google/Gemini under one vault key (see design decision 5)."""
        assert _PROVIDER_VAULT_KEYS["gemini"] == "google"

    def test_ollama_has_empty_sentinel(self) -> None:
        """Ollama is local — no key needed. Sentinel '' signals skip."""
        assert _PROVIDER_VAULT_KEYS["ollama"] == ""

    def test_deepgram_shared_key(self) -> None:
        """Deepgram serves both STT and TTS via the same vault key."""
        assert _PROVIDER_VAULT_KEYS["deepgram"] == "deepgram"


class TestResolveApiKey:
    """Phase 1 — async helper with 4 code paths."""

    @pytest.mark.asyncio
    async def test_returns_none_when_tenant_ctx_is_none(self) -> None:
        """No tenant context → no vault call, return None so plugin falls back to env."""
        result = await _resolve_api_key("deepgram", None)
        assert result is None

    @pytest.mark.asyncio
    async def test_calls_get_secret_with_mapped_vault_key(self) -> None:
        """Known provider + ctx present → vault lookup with mapped key."""
        mock_ctx = AsyncMock()
        mock_ctx.get_secret = AsyncMock(return_value="dg-secret-value")

        result = await _resolve_api_key("deepgram", mock_ctx)

        mock_ctx.get_secret.assert_awaited_once_with("deepgram")
        assert result == "dg-secret-value"

    @pytest.mark.asyncio
    async def test_gemini_resolves_under_google_key(self) -> None:
        """Provider name 'gemini' maps to vault key 'google' (unified)."""
        mock_ctx = AsyncMock()
        mock_ctx.get_secret = AsyncMock(return_value="google-key")

        result = await _resolve_api_key("gemini", mock_ctx)

        mock_ctx.get_secret.assert_awaited_once_with("google")
        assert result == "google-key"

    @pytest.mark.asyncio
    async def test_unknown_provider_returns_none_without_vault_call(self) -> None:
        """Provider not in the dict → None, NO vault call (silent fallback)."""
        mock_ctx = AsyncMock()
        mock_ctx.get_secret = AsyncMock()

        result = await _resolve_api_key("some_future_provider", mock_ctx)

        mock_ctx.get_secret.assert_not_awaited()
        assert result is None

    @pytest.mark.asyncio
    async def test_ollama_skipped_without_vault_call(self) -> None:
        """Ollama sentinel '' → None, NO vault call (local, no key)."""
        mock_ctx = AsyncMock()
        mock_ctx.get_secret = AsyncMock()

        result = await _resolve_api_key("ollama", mock_ctx)

        mock_ctx.get_secret.assert_not_awaited()
        assert result is None
