"""Tests para OpenAIRealtime — default model y as_livekit_plugin."""
from unittest.mock import MagicMock, patch

from core.llm.openai_realtime import OpenAIRealtime


def test_default_model_is_gpt_realtime_1_5():
    instance = OpenAIRealtime()
    assert instance.model == "gpt-realtime-1.5"


def test_as_livekit_plugin_passes_model_to_realtime_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with patch("core.llm.openai_realtime.lk_realtime.RealtimeModel") as mock_realtime:
        mock_realtime.return_value = MagicMock()
        instance = OpenAIRealtime()
        instance.as_livekit_plugin()
        call_kwargs = mock_realtime.call_args[1]
        assert call_kwargs["model"] == "gpt-realtime-1.5"
