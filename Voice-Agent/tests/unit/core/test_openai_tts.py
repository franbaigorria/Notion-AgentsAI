"""Tests para OpenAITTS."""
from unittest.mock import AsyncMock, MagicMock, patch


from core.tts.base import TTSResult
from core.tts.openai_tts import OpenAITTS


def test_default_params():
    tts = OpenAITTS()
    assert tts.voice == "ash"
    assert tts.model == "gpt-4o-mini-tts"
    assert tts.instructions is None
    assert tts.speed == 1.0


def test_as_livekit_plugin_calls_lk_tts_without_instructions():
    with (
        patch("livekit.plugins.openai.TTS") as mock_lk_tts,
        patch("core.tts.openai_tts._make_preprocessed_tts") as mock_wrap,
    ):
        mock_lk_tts.return_value = MagicMock()
        mock_wrap.return_value = MagicMock()

        tts = OpenAITTS()
        tts.as_livekit_plugin()

        call_kwargs = mock_lk_tts.call_args[1]
        assert call_kwargs["voice"] == "ash"
        assert call_kwargs["model"] == "gpt-4o-mini-tts"
        assert call_kwargs["speed"] == 1.0
        assert "instructions" not in call_kwargs


def test_as_livekit_plugin_passes_instructions_when_set():
    with (
        patch("livekit.plugins.openai.TTS") as mock_lk_tts,
        patch("core.tts.openai_tts._make_preprocessed_tts") as mock_wrap,
    ):
        mock_lk_tts.return_value = MagicMock()
        mock_wrap.return_value = MagicMock()

        tts = OpenAITTS(instructions="sé formal")
        tts.as_livekit_plugin()

        call_kwargs = mock_lk_tts.call_args[1]
        assert call_kwargs["instructions"] == "sé formal"


def test_as_livekit_plugin_wraps_with_strip_tone_tags():
    with (
        patch("livekit.plugins.openai.TTS") as mock_lk_tts,
        patch("core.tts.openai_tts._make_preprocessed_tts") as mock_wrap,
        patch("core.tts.openai_tts.strip_tone_tags") as mock_strip,
    ):
        mock_plugin = MagicMock()
        mock_lk_tts.return_value = mock_plugin
        mock_wrap.return_value = MagicMock()

        tts = OpenAITTS()
        tts.as_livekit_plugin()

        mock_wrap.assert_called_once_with(mock_plugin, mock_strip)


async def test_synthesize_calls_openai_sdk_audio_speech_create(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    mock_response = MagicMock()

    async def _aiter_bytes():
        yield b"chunk1"

    mock_response.aiter_bytes = _aiter_bytes
    mock_create = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.audio.speech.create = mock_create

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        tts = OpenAITTS()
        await tts.synthesize("hola", "")

        mock_create.assert_called_once_with(
            model="gpt-4o-mini-tts",
            voice="ash",
            input="hola",
        )


async def test_synthesize_streams_bytes(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    mock_response = MagicMock()

    async def _aiter_bytes():
        yield b"chunk1"
        yield b"chunk2"

    mock_response.aiter_bytes = _aiter_bytes
    mock_create = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.audio.speech.create = mock_create

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        tts = OpenAITTS()
        stream = await tts.synthesize("hola", "")
        chunks = [chunk async for chunk in stream]

    assert chunks == [b"chunk1", b"chunk2"]


def test_estimate_cost_returns_tts_result():
    tts = OpenAITTS()
    text = "hola mundo"
    result = tts.estimate_cost(text)
    expected_cost = len(text) * 0.25 * 0.0000024
    assert abs(result.cost_usd - expected_cost) < 1e-10
    assert result.provider == "openai"
    assert isinstance(result, TTSResult)
