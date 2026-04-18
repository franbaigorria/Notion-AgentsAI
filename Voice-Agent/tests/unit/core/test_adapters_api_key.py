"""Unit tests — adapter api_key forwarding (Phase 2 RED).

Covers all STT / LLM / TTS / Realtime adapters:
  - accept `api_key: str | None = None` in __init__ without error
  - custom adapters (GeminiTTS, FishSpeechTTS, CartesiaTTS) fall back to env
    ONLY when api_key=None (explicit value takes precedence)

Does NOT spin up LiveKit plugins — constructor + state checks only.
Full plug-through verification happens in test_builders_with_tenant_ctx.py.
"""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("ENV", "test")


# ---------------------------------------------------------------------------
# STT adapters
# ---------------------------------------------------------------------------


class TestSTTAdaptersAcceptApiKey:
    def test_deepgram_stt_accepts_api_key(self) -> None:
        from core.stt.deepgram import DeepgramSTT

        stt = DeepgramSTT(api_key="dg-test")
        assert stt.api_key == "dg-test"

    def test_deepgram_stt_defaults_to_none(self) -> None:
        from core.stt.deepgram import DeepgramSTT

        stt = DeepgramSTT()
        assert stt.api_key is None

    def test_elevenlabs_stt_accepts_api_key(self) -> None:
        from core.stt.elevenlabs_stt import ElevenLabsSTT

        stt = ElevenLabsSTT(api_key="el-test")
        assert stt.api_key == "el-test"

    def test_openai_stt_accepts_api_key(self) -> None:
        from core.stt.openai_stt import OpenAISTT

        stt = OpenAISTT(api_key="oa-test")
        assert stt.api_key == "oa-test"


# ---------------------------------------------------------------------------
# LLM adapters
# ---------------------------------------------------------------------------


class TestLLMAdaptersAcceptApiKey:
    def test_claude_accepts_api_key(self) -> None:
        from core.llm.claude import ClaudeLLM

        llm = ClaudeLLM(api_key="cl-test")
        assert llm.api_key == "cl-test"

    def test_openai_llm_accepts_api_key(self) -> None:
        from core.llm.openai import OpenAILLM

        llm = OpenAILLM(api_key="oa-test")
        assert llm.api_key == "oa-test"

    def test_groq_accepts_api_key_without_env(self) -> None:
        """GroqLLM used to require GROQ_API_KEY in env at __init__ — must still boot
        when explicit api_key is passed, regardless of env."""
        from core.llm.groq import GroqLLM

        env_without = {k: v for k, v in os.environ.items() if k != "GROQ_API_KEY"}
        with patch.dict(os.environ, env_without, clear=True):
            llm = GroqLLM(api_key="groq-test")
            assert llm.api_key == "groq-test"

    def test_gemini_accepts_api_key_without_env(self) -> None:
        """GeminiLLM used to require GEMINI_API_KEY in env at __init__ — must still boot
        when explicit api_key is passed, regardless of env."""
        from core.llm.gemini import GeminiLLM

        env_without = {
            k: v
            for k, v in os.environ.items()
            if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")
        }
        with patch.dict(os.environ, env_without, clear=True):
            llm = GeminiLLM(api_key="g-test")
            assert llm.api_key == "g-test"

    def test_ollama_accepts_api_key_param_but_ignores_it(self) -> None:
        """Ollama is local — api_key kwarg is interface uniformity, never used."""
        from core.llm.ollama import OllamaLLM

        llm = OllamaLLM(api_key="ignored")
        # Ollama hardcodes "ollama" as the key sent to its OpenAI-compat endpoint
        assert llm.base_url.startswith("http://")

    def test_openai_realtime_accepts_api_key(self) -> None:
        from core.llm.openai_realtime import OpenAIRealtime

        rt = OpenAIRealtime(api_key="oa-rt-test")
        assert rt.api_key == "oa-rt-test"


# ---------------------------------------------------------------------------
# TTS adapters
# ---------------------------------------------------------------------------


class TestTTSAdaptersAcceptApiKey:
    def test_deepgram_tts_accepts_api_key(self) -> None:
        from core.tts.deepgram import DeepgramTTS

        tts = DeepgramTTS(api_key="dg-tts-test")
        assert tts.api_key == "dg-tts-test"

    def test_elevenlabs_tts_accepts_api_key(self) -> None:
        from core.tts.elevenlabs import ElevenLabsTTS

        tts = ElevenLabsTTS(voice_id="vid", api_key="el-tts-test")
        assert tts.api_key == "el-tts-test"

    def test_openai_tts_accepts_api_key(self) -> None:
        from core.tts.openai_tts import OpenAITTS

        tts = OpenAITTS(api_key="oa-tts-test")
        assert tts.api_key == "oa-tts-test"


# ---------------------------------------------------------------------------
# Custom adapters — env fallback refactor
# ---------------------------------------------------------------------------


class TestCartesiaTTSEnvFallback:
    """CartesiaTTS used to read env INSIDE as_livekit_plugin — now reads at __init__."""

    def test_explicit_api_key_preferred_over_env(self) -> None:
        from core.tts.cartesia import CartesiaTTS

        with patch.dict(os.environ, {"CARTESIA_API_KEY": "env-value"}):
            tts = CartesiaTTS(voice_id="vid", api_key="explicit-value")
            assert tts.api_key == "explicit-value"

    def test_falls_back_to_env_when_api_key_is_none(self) -> None:
        from core.tts.cartesia import CartesiaTTS

        with patch.dict(os.environ, {"CARTESIA_API_KEY": "env-value"}):
            tts = CartesiaTTS(voice_id="vid")
            assert tts.api_key == "env-value"


class TestGeminiTTSEnvFallbackChain:
    """GeminiTTS used to hardcode GEMINI_API_KEY — now falls back to
    GOOGLE_API_KEY → GEMINI_API_KEY in that order."""

    def test_explicit_api_key_preferred_over_env(self) -> None:
        from core.tts.gemini_tts import GeminiTTS

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "env-g", "GEMINI_API_KEY": "env-gm"}):
            tts = GeminiTTS(api_key="explicit")
            assert tts.api_key == "explicit"

    def test_prefers_google_api_key_over_gemini_api_key(self) -> None:
        from core.tts.gemini_tts import GeminiTTS

        env = {k: v for k, v in os.environ.items() if k not in ("GOOGLE_API_KEY", "GEMINI_API_KEY")}
        env["GOOGLE_API_KEY"] = "from-google"
        env["GEMINI_API_KEY"] = "from-gemini"
        with patch.dict(os.environ, env, clear=True):
            tts = GeminiTTS()
            assert tts.api_key == "from-google"

    def test_falls_back_to_gemini_api_key_when_google_absent(self) -> None:
        from core.tts.gemini_tts import GeminiTTS

        env = {k: v for k, v in os.environ.items() if k not in ("GOOGLE_API_KEY", "GEMINI_API_KEY")}
        env["GEMINI_API_KEY"] = "from-gemini"
        with patch.dict(os.environ, env, clear=True):
            tts = GeminiTTS()
            assert tts.api_key == "from-gemini"


class TestFishSpeechTTSEnvFallback:
    """FishSpeechTTS used to read env directly in __init__ — now accepts api_key."""

    def test_explicit_api_key_preferred_over_env(self) -> None:
        from core.tts.fish_speech import FishSpeechTTS

        with patch.dict(os.environ, {"FISH_AUDIO_API_KEY": "env-value"}):
            tts = FishSpeechTTS(api_key="explicit")
            assert tts.api_key == "explicit"

    def test_falls_back_to_env_when_api_key_is_none(self) -> None:
        from core.tts.fish_speech import FishSpeechTTS

        with patch.dict(os.environ, {"FISH_AUDIO_API_KEY": "env-value"}):
            tts = FishSpeechTTS()
            assert tts.api_key == "env-value"
