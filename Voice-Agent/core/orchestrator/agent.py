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

    providers = {"deepgram": lambda: DeepgramSTT(
        model=config.get("stt_model", "nova-2"),
        language=config.get("language", "es"),
    )}

    name = config.get("stt_provider", "deepgram")
    if name not in providers:
        raise ValueError(f"STT provider desconocido: '{name}'. Disponibles: {list(providers)}")

    return providers[name]().as_livekit_plugin()


def build_llm(config: dict):
    from core.llm.claude import ClaudeLLM

    providers = {"claude": lambda: ClaudeLLM(
        model=config.get("llm_model", "claude-sonnet-4-6"),
    )}

    name = config.get("llm_provider", "claude")
    if name not in providers:
        raise ValueError(f"LLM provider desconocido: '{name}'. Disponibles: {list(providers)}")

    return providers[name]().as_livekit_plugin()


def build_tts(config: dict):
    from core.tts.elevenlabs import ElevenLabsTTS

    providers = {"elevenlabs": lambda: ElevenLabsTTS(
        voice_id=config["voice_id"],
        model=config.get("tts_model", "eleven_multilingual_v2"),
    )}

    name = config.get("tts_provider", "elevenlabs")
    if name not in providers:
        raise ValueError(f"TTS provider desconocido: '{name}'. Disponibles: {list(providers)}")

    return providers[name]().as_livekit_plugin()


async def entrypoint(ctx: JobContext) -> None:
    vertical_name = os.environ.get("VERTICAL", "clinica")
    config = load_vertical(vertical_name)

    await ctx.connect()

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=build_stt(config),
        llm=build_llm(config),
        tts=build_tts(config),
    )

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
