"""Shared builders — Voice Agent Platform.

Funciones compartidas para cargar configuración del vertical y construir
los componentes (STT, LLM, TTS, Realtime) que usan los agentes en apps/.

Los entry points están en:
    apps/pipeline/agent.py   — STT → LLM → TTS
    apps/realtime/agent.py   — OpenAI Speech-to-Speech
    apps/launcher.py         — Despacha según AGENT_MODE

Variables de entorno requeridas:
    VERTICAL            nombre del directorio en verticals/ (default: clinica)
    LIVEKIT_URL         URL del servidor LiveKit
    LIVEKIT_API_KEY     API key de LiveKit
    LIVEKIT_API_SECRET  API secret de LiveKit
"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


load_dotenv()

VERTICALS_DIR = Path(__file__).parent.parent.parent / "verticals"


def load_vertical(name: str) -> dict:
    """Carga config.yaml y persona.md del vertical indicado."""
    path = VERTICALS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Vertical '{name}' no encontrado en {VERTICALS_DIR}")

    with open(path / "config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    with open(path / "persona.md", encoding="utf-8") as f:
        config["persona"] = f.read()

    return config


def build_stt(config: dict):
    from core.stt.deepgram import DeepgramSTT
    from core.stt.elevenlabs_stt import ElevenLabsSTT
    from core.stt.openai_stt import OpenAISTT

    providers = {
        "deepgram": lambda: DeepgramSTT(
            model=config.get("stt_model", "nova-3"),
            language=config.get("language", "es"),
        ),
        "elevenlabs": lambda: ElevenLabsSTT(
            model=config.get("stt_model", "scribe_v2_realtime"),
            language=config.get("language", "es"),
        ),
        "openai": lambda: OpenAISTT(
            model=config.get("stt_model", "gpt-4o-mini-transcribe"),
            language=config.get("language", "es"),
            use_realtime=config.get("stt_use_realtime", True),
        ),
    }

    name = config.get("stt_provider", "deepgram")
    if name not in providers:
        raise ValueError(f"STT provider desconocido: '{name}'. Disponibles: {list(providers)}")

    return providers[name]().as_livekit_plugin()


def is_realtime_mode(config: dict) -> bool:
    """True si el modo es realtime (speech-to-speech, bypassea STT+TTS)."""
    return config.get("mode", "pipeline") == "realtime"


def build_realtime_llm(config: dict):
    """Construye el modelo Realtime speech-to-speech de OpenAI."""
    from core.llm.openai_realtime import OpenAIRealtime

    realtime_cfg = config.get("realtime", {})
    return OpenAIRealtime(
        model=realtime_cfg.get("model", "gpt-4o-mini-realtime-preview"),
        voice=realtime_cfg.get("voice", "ash"),
        temperature=realtime_cfg.get("temperature"),
        speed=realtime_cfg.get("speed"),
    ).as_livekit_plugin()


def build_llm(config: dict):
    from core.llm.claude import ClaudeLLM
    from core.llm.gemini import GeminiLLM
    from core.llm.groq import GroqLLM
    from core.llm.ollama import OllamaLLM
    from core.llm.openai import OpenAILLM

    providers = {
        "claude": lambda: ClaudeLLM(model=config.get("llm_model", "claude-sonnet-4-6")),
        "openai": lambda: OpenAILLM(model=config.get("llm_model", "gpt-4o-mini")),
        "ollama": lambda: OllamaLLM(model=config.get("llm_model", "gemma4:e4b")),
        "groq": lambda: GroqLLM(model=config.get("llm_model", "llama-3.1-8b-instant")),
        "gemini": lambda: GeminiLLM(model=config.get("llm_model", "gemini-3.1-flash-lite")),
    }

    name = config.get("llm_provider", "claude")
    if name not in providers:
        raise ValueError(f"LLM provider desconocido: '{name}'. Disponibles: {list(providers)}")

    return providers[name]().as_livekit_plugin()


def build_tts(config: dict):
    from core.tts.deepgram import DeepgramTTS
    from core.tts.elevenlabs import ElevenLabsTTS
    from core.tts.cartesia import CartesiaTTS
    from core.tts.fish_speech import FishSpeechTTS
    from core.tts.gemini_tts import GeminiTTS
    from core.tts.openai_tts import OpenAITTS

    voice_settings = config.get("voice_settings", {})
    providers = {
        "elevenlabs": lambda: ElevenLabsTTS(
            voice_id=os.environ.get("ELEVENLABS_VOICE_ID") or config.get("voice_id", ""),
            model=config.get("tts_model", "eleven_multilingual_v2"),
            stability=voice_settings.get("stability"),
            similarity_boost=voice_settings.get("similarity_boost"),
            style=voice_settings.get("style"),
            speed=voice_settings.get("speed"),
            apply_text_normalization=config.get("apply_text_normalization", "auto"),
        ),
        "deepgram": lambda: DeepgramTTS(
            model=config.get("tts_model", "aura-2-antonia-es"),
        ),
        "cartesia": lambda: CartesiaTTS(
            voice_id=os.environ.get("CARTESIA_VOICE_ID") or config.get("voice_id", ""),
            model=config.get("tts_model", "sonic-multilingual"),
        ),
        "fish_speech": lambda: FishSpeechTTS(
            voice_id=os.environ.get("FISH_AUDIO_VOICE_ID") or config.get("voice_id", ""),
            model=config.get("tts_model", ""),
        ),
        "openai": lambda: OpenAITTS(
            voice=config.get("voice_id", "ash"),
            model=config.get("tts_model", "gpt-4o-mini-tts"),
            instructions=config.get("tts_instructions"),
            speed=voice_settings.get("speed", 1.0),
        ),
        "gemini": lambda: GeminiTTS(
            voice=config.get("voice_id", "Charon"),
            model=config.get("tts_model", "gemini-3.1-flash-tts-preview"),
            instructions=config.get("tts_instructions"),
        ),
    }

    name = config.get("tts_provider", "elevenlabs")
    if name not in providers:
        raise ValueError(f"TTS provider desconocido: '{name}'. Disponibles: {list(providers)}")

    return providers[name]().as_livekit_plugin()

