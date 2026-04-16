"""Tests para GeminiTTS — TDD Phase 1."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def gemini_env(monkeypatch):
    """Setea GEMINI_API_KEY para todos los tests de construcción."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")


def _make_audio_response(data: bytes = b"fake_audio", mime_type: str = "audio/L16;codec=pcm;rate=24000"):
    """Construye un mock de respuesta con un audio part."""
    mock_inline_data = MagicMock()
    mock_inline_data.data = data
    mock_inline_data.mime_type = mime_type

    mock_part = MagicMock()
    mock_part.inline_data = mock_inline_data

    mock_content = MagicMock()
    mock_content.parts = [mock_part]

    mock_candidate = MagicMock()
    mock_candidate.content = mock_content

    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]
    return mock_response


# ── Construction ──────────────────────────────────────────────────────────────


def test_default_params(gemini_env):
    with patch("core.tts.gemini_tts.genai.Client"):
        from core.tts.gemini_tts import GeminiTTS

        g = GeminiTTS()
        assert g.voice == "Charon"
        assert g.model_name == "gemini-3.1-flash-tts-preview"
        assert g.instructions is None
        assert g.sample_rate == 24000
        assert g.num_channels == 1


def test_custom_params(gemini_env):
    with patch("core.tts.gemini_tts.genai.Client"):
        from core.tts.gemini_tts import GeminiTTS

        g = GeminiTTS(voice="Puck", model="gemini-custom", instructions="sé formal")
        assert g.voice == "Puck"
        assert g.model_name == "gemini-custom"
        assert g.instructions == "sé formal"


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from core.tts.gemini_tts import GeminiTTS

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiTTS()


def test_empty_api_key_raises(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    from core.tts.gemini_tts import GeminiTTS

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiTTS()


def test_capabilities(gemini_env):
    with patch("core.tts.gemini_tts.genai.Client"):
        from core.tts.gemini_tts import GeminiTTS

        g = GeminiTTS()
        assert g.capabilities.streaming is False
        assert g.sample_rate == 24000
        assert g.num_channels == 1


# ── as_livekit_plugin ─────────────────────────────────────────────────────────


def test_as_livekit_plugin_returns_self(gemini_env):
    with patch("core.tts.gemini_tts.genai.Client"):
        from core.tts.gemini_tts import GeminiTTS

        g = GeminiTTS()
        assert g.as_livekit_plugin() is g


# ── synthesize ────────────────────────────────────────────────────────────────


async def test_synthesize_strips_tone_tags(gemini_env):
    with patch("core.tts.gemini_tts.genai.Client"):
        from core.tts.gemini_tts import GeminiTTS, _GeminiChunkedStream

        g = GeminiTTS()
        stream = g.synthesize("<tone:cheerful>Hola mundo</tone:cheerful>")
        assert isinstance(stream, _GeminiChunkedStream)
        assert stream._input_text == "Hola mundo"


async def test_synthesize_returns_chunked_stream(gemini_env):
    with patch("core.tts.gemini_tts.genai.Client"):
        from core.tts.gemini_tts import GeminiTTS, _GeminiChunkedStream

        g = GeminiTTS()
        stream = g.synthesize("hola")
        assert isinstance(stream, _GeminiChunkedStream)


# ── _run() happy path ─────────────────────────────────────────────────────────


async def test_run_calls_generate_content_with_correct_model(gemini_env):
    mock_response = _make_audio_response()
    mock_generate = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = mock_generate

    with patch("core.tts.gemini_tts.genai.Client", return_value=mock_client):
        from core.tts.gemini_tts import GeminiTTS

        g = GeminiTTS()
        stream = g.synthesize("hola mundo")
        await stream._run(MagicMock())

        mock_generate.assert_called_once()
        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["model"] == "gemini-3.1-flash-tts-preview"
        assert call_kwargs["contents"] == "hola mundo"


async def test_run_pushes_audio_to_emitter(gemini_env):
    mock_response = _make_audio_response(b"pcm_bytes")
    mock_generate = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = mock_generate

    with patch("core.tts.gemini_tts.genai.Client", return_value=mock_client):
        from core.tts.gemini_tts import GeminiTTS

        g = GeminiTTS()
        stream = g.synthesize("hola")
        mock_emitter = MagicMock()
        await stream._run(mock_emitter)

        mock_emitter.initialize.assert_called_once()
        init_kwargs = mock_emitter.initialize.call_args.kwargs
        assert init_kwargs["sample_rate"] == 24000
        assert init_kwargs["num_channels"] == 1
        assert init_kwargs["mime_type"] == "audio/pcm"

        mock_emitter.push.assert_called_once_with(b"pcm_bytes")
        mock_emitter.flush.assert_called_once()


async def test_run_without_instructions_sends_raw_text(gemini_env):
    mock_generate = AsyncMock(return_value=_make_audio_response())
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = mock_generate

    with patch("core.tts.gemini_tts.genai.Client", return_value=mock_client):
        from core.tts.gemini_tts import GeminiTTS

        g = GeminiTTS()  # instructions=None
        stream = g.synthesize("hola")
        await stream._run(MagicMock())

        assert mock_generate.call_args.kwargs["contents"] == "hola"


async def test_run_with_instructions_prepends_text(gemini_env):
    mock_generate = AsyncMock(return_value=_make_audio_response())
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = mock_generate

    with patch("core.tts.gemini_tts.genai.Client", return_value=mock_client):
        from core.tts.gemini_tts import GeminiTTS

        g = GeminiTTS(instructions="Sé amable")
        stream = g.synthesize("hola")
        await stream._run(MagicMock())

        assert mock_generate.call_args.kwargs["contents"] == 'Sé amable:\n"hola"'


# ── _run() error paths ────────────────────────────────────────────────────────


async def test_run_empty_candidates_raises_api_status_error(gemini_env):
    from livekit.agents import APIStatusError

    mock_response = MagicMock()
    mock_response.candidates = []
    mock_generate = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = mock_generate

    with patch("core.tts.gemini_tts.genai.Client", return_value=mock_client):
        from core.tts.gemini_tts import GeminiTTS

        g = GeminiTTS()
        stream = g.synthesize("hola")
        with pytest.raises(APIStatusError):
            await stream._run(MagicMock())


async def test_run_generic_exception_maps_to_api_connection_error(gemini_env):
    from livekit.agents import APIConnectionError

    mock_generate = AsyncMock(side_effect=OSError("network error"))
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = mock_generate

    with patch("core.tts.gemini_tts.genai.Client", return_value=mock_client):
        from core.tts.gemini_tts import GeminiTTS

        g = GeminiTTS()
        stream = g.synthesize("hola")
        with pytest.raises(APIConnectionError):
            await stream._run(MagicMock())


# ── estimate_cost ─────────────────────────────────────────────────────────────


def test_estimate_cost_returns_tts_result(gemini_env):
    from core.tts.base import TTSResult

    with patch("core.tts.gemini_tts.genai.Client"):
        from core.tts.gemini_tts import GeminiTTS

        g = GeminiTTS()
        result = g.estimate_cost("hola mundo")
        assert result.provider == "gemini"
        assert isinstance(result, TTSResult)
        assert result.cost_usd > 0


# ── build_tts() integration ───────────────────────────────────────────────────


def test_build_tts_gemini_returns_livekit_plugin(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch("core.tts.gemini_tts.genai.Client"):
        from core.orchestrator.agent import build_tts

        result = build_tts({"tts_provider": "gemini", "voice_settings": {}})
        # GeminiTTS.as_livekit_plugin() returns self — result IS a GeminiTTS
        from core.tts.gemini_tts import GeminiTTS

        assert isinstance(result, GeminiTTS)


def test_build_tts_gemini_passes_voice_from_config(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch("core.tts.gemini_tts.genai.Client"):
        from core.orchestrator.agent import build_tts
        from core.tts.gemini_tts import GeminiTTS

        result = build_tts({"tts_provider": "gemini", "voice_id": "Puck", "voice_settings": {}})
        assert isinstance(result, GeminiTTS)
        assert result.voice == "Puck"


def test_build_tts_gemini_default_voice_is_charon(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch("core.tts.gemini_tts.genai.Client"):
        from core.orchestrator.agent import build_tts
        from core.tts.gemini_tts import GeminiTTS

        result = build_tts({"tts_provider": "gemini", "voice_settings": {}})
        assert isinstance(result, GeminiTTS)
        assert result.voice == "Charon"
