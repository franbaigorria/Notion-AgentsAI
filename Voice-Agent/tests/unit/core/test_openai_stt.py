"""Tests para OpenAISTT."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.stt.base import STTResult
from core.stt.openai_stt import OpenAISTT


def test_default_params():
    stt = OpenAISTT()
    assert stt.model == "gpt-4o-mini-transcribe"
    assert stt.language == "es"
    assert stt.use_realtime is True


def test_as_livekit_plugin_passes_correct_args():
    with patch("livekit.plugins.openai.STT") as mock_lk_stt:
        mock_lk_stt.return_value = MagicMock()
        stt = OpenAISTT()
        stt.as_livekit_plugin()

        call_kwargs = mock_lk_stt.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini-transcribe"
        assert call_kwargs["language"] == "es"
        assert call_kwargs["use_realtime"] is True


async def test_transcribe_raises_not_implemented_when_use_realtime_true():
    stt = OpenAISTT(use_realtime=True)
    with pytest.raises(NotImplementedError):
        await stt.transcribe(b"audio", "es")


async def test_transcribe_calls_openai_sdk_when_use_realtime_false(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    mock_result = MagicMock()
    mock_result.text = "hola"
    mock_create = AsyncMock(return_value=mock_result)
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = mock_create

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        stt = OpenAISTT(use_realtime=False)
        await stt.transcribe(b"audio_bytes", "es")

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini-transcribe"
        assert call_kwargs["language"] == "es"
        assert call_kwargs["file"] == b"audio_bytes"


async def test_transcribe_returns_stt_result(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    mock_result = MagicMock()
    mock_result.text = "hola"
    mock_create = AsyncMock(return_value=mock_result)
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = mock_create

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        stt = OpenAISTT(use_realtime=False)
        result = await stt.transcribe(b"audio_bytes", "es")

    assert result.transcript == "hola"
    assert result.provider == "openai"
    assert result.cost_usd > 0
    assert isinstance(result, STTResult)
