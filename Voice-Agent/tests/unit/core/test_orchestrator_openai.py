"""Tests para los builders de OpenAI en core/orchestrator/agent.py."""
import pytest
from unittest.mock import MagicMock, patch

from core.orchestrator.agent import build_stt, build_tts


@pytest.fixture
def config_openai_tts():
    return {
        "tts_provider": "openai",
        "voice_id": "ash",
        "tts_model": "gpt-4o-mini-tts",
        "voice_settings": {},
    }


@pytest.fixture
def config_openai_stt():
    return {
        "stt_provider": "openai",
        "stt_model": "gpt-4o-mini-transcribe",
        "language": "es",
    }


def test_build_tts_openai_returns_livekit_plugin(config_openai_tts):
    with patch("core.tts.openai_tts.OpenAITTS") as mock_openai_tts:
        mock_instance = MagicMock()
        mock_plugin = MagicMock()
        mock_openai_tts.return_value = mock_instance
        mock_instance.as_livekit_plugin.return_value = mock_plugin

        result = build_tts(config_openai_tts)

        assert result is mock_plugin


def test_build_tts_openai_passes_voice_id(config_openai_tts):
    with patch("core.tts.openai_tts.OpenAITTS") as mock_openai_tts:
        mock_openai_tts.return_value = MagicMock()

        build_tts(config_openai_tts)

        call_kwargs = mock_openai_tts.call_args[1]
        assert call_kwargs["voice"] == "ash"


def test_build_tts_openai_passes_instructions_from_config(config_openai_tts):
    config_openai_tts["tts_instructions"] = "sé formal"
    with patch("core.tts.openai_tts.OpenAITTS") as mock_openai_tts:
        mock_openai_tts.return_value = MagicMock()

        build_tts(config_openai_tts)

        call_kwargs = mock_openai_tts.call_args[1]
        assert call_kwargs["instructions"] == "sé formal"


def test_build_tts_openai_passes_speed_from_voice_settings(config_openai_tts):
    config_openai_tts["voice_settings"] = {"speed": 1.2}
    with patch("core.tts.openai_tts.OpenAITTS") as mock_openai_tts:
        mock_openai_tts.return_value = MagicMock()

        build_tts(config_openai_tts)

        call_kwargs = mock_openai_tts.call_args[1]
        assert call_kwargs["speed"] == 1.2


def test_build_stt_openai_returns_livekit_plugin(config_openai_stt):
    with patch("core.stt.openai_stt.OpenAISTT") as mock_openai_stt:
        mock_instance = MagicMock()
        mock_plugin = MagicMock()
        mock_openai_stt.return_value = mock_instance
        mock_instance.as_livekit_plugin.return_value = mock_plugin

        result = build_stt(config_openai_stt)

        assert result is mock_plugin


def test_build_stt_openai_passes_model_language_use_realtime(config_openai_stt):
    config_openai_stt["stt_use_realtime"] = False
    with patch("core.stt.openai_stt.OpenAISTT") as mock_openai_stt:
        mock_openai_stt.return_value = MagicMock()

        build_stt(config_openai_stt)

        call_kwargs = mock_openai_stt.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini-transcribe"
        assert call_kwargs["language"] == "es"
        assert call_kwargs["use_realtime"] is False


def test_build_tts_unknown_provider_raises_value_error():
    with pytest.raises(ValueError, match="nonexistent"):
        build_tts({"tts_provider": "nonexistent"})


def test_build_stt_unknown_provider_raises_value_error():
    with pytest.raises(ValueError, match="nonexistent"):
        build_stt({"stt_provider": "nonexistent"})
