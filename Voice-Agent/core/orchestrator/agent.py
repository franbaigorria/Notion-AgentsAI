"""Orquestador principal — Voice Agent Platform.

Carga la configuración del vertical y arranca un AgentSession de LiveKit.

Uso:
    VERTICAL=clinica python -m core.orchestrator.agent dev

Variables de entorno requeridas:
    VERTICAL            nombre del directorio en verticals/ (default: clinica)
    LIVEKIT_URL         URL del servidor LiveKit
    LIVEKIT_API_KEY     API key de LiveKit
    LIVEKIT_API_SECRET  API secret de LiveKit
    ANTHROPIC_API_KEY   API key de Anthropic
    ELEVENLABS_API_KEY  API key de ElevenLabs
    DEEPGRAM_API_KEY    API key de Deepgram
"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.agents.metrics import log_metrics
from livekit.plugins import silero

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

    providers = {
        "deepgram": lambda: DeepgramSTT(
            model=config.get("stt_model", "nova-3"),
            language=config.get("language", "es"),
        ),
        "elevenlabs": lambda: ElevenLabsSTT(
            model=config.get("stt_model", "scribe_v2_realtime"),
            language=config.get("language", "es"),
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
    from core.llm.groq import GroqLLM
    from core.llm.ollama import OllamaLLM
    from core.llm.openai import OpenAILLM

    providers = {
        "claude": lambda: ClaudeLLM(model=config.get("llm_model", "claude-sonnet-4-6")),
        "openai": lambda: OpenAILLM(model=config.get("llm_model", "gpt-4o-mini")),
        "ollama": lambda: OllamaLLM(model=config.get("llm_model", "gemma4:e4b")),
        "groq": lambda: GroqLLM(model=config.get("llm_model", "llama-3.1-8b-instant")),
    }

    name = config.get("llm_provider", "claude")
    if name not in providers:
        raise ValueError(f"LLM provider desconocido: '{name}'. Disponibles: {list(providers)}")

    return providers[name]().as_livekit_plugin()


def build_tts(config: dict):
    from core.tts.deepgram import DeepgramTTS
    from core.tts.elevenlabs import ElevenLabsTTS
    from core.tts.cartesia import CartesiaTTS

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
    }

    name = config.get("tts_provider", "elevenlabs")
    if name not in providers:
        raise ValueError(f"TTS provider desconocido: '{name}'. Disponibles: {list(providers)}")

    return providers[name]().as_livekit_plugin()


async def entrypoint(ctx: JobContext) -> None:
    vertical_name = os.environ.get("VERTICAL", "clinica")
    config = load_vertical(vertical_name)

    await ctx.connect()

    if is_realtime_mode(config):
        # Realtime: un único modelo speech-to-speech reemplaza STT + LLM + TTS
        rt = config.get("realtime", {})
        print(f"[MODE=realtime] model={rt.get('model')} voice={rt.get('voice')}")
        session = AgentSession(llm=build_realtime_llm(config))
    else:
        # Pipeline clásico: STT → LLM → TTS
        print(
            f"[MODE=pipeline] "
            f"STT={config.get('stt_provider')}/{config.get('stt_model')} "
            f"LLM={config.get('llm_provider')}/{config.get('llm_model')} "
            f"TTS={config.get('tts_provider')}/{config.get('tts_model')}"
        )
        session = AgentSession(
            vad=silero.VAD.load(),
            stt=build_stt(config),
            llm=build_llm(config),
            tts=build_tts(config),
            preemptive_generation=True,
        )

    session.on("metrics_collected", lambda ev: log_metrics(ev.metrics))

    await session.start(
        agent=Agent(instructions=config["persona"]),
        room=ctx.room,
    )

    await session.generate_reply(
        instructions=config.get(
            "greeting",
            "Saludá al usuario con calidez y preguntale en qué podés ayudarlo.",
        )
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
