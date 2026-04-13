"""Pipeline Agent — STT → LLM → TTS.

Arquitectura clásica de 3 saltos con voz custom (ElevenLabs/Cartesia).
Soporta cualquier combinación de providers configurados en config.yaml.

Uso directo (dev):
    AGENT_MODE=pipeline uv run python -m apps.pipeline.agent dev

En producción se levanta via apps.launcher.
"""

import os

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.agents.metrics import log_metrics
from livekit.plugins import silero

from core.orchestrator.agent import build_llm, build_stt, build_tts, load_vertical


async def entrypoint(ctx: JobContext) -> None:
    vertical_name = os.environ.get("VERTICAL", "clinica")
    config = load_vertical(vertical_name)

    print(
        f"[MODE=pipeline] "
        f"STT={config.get('stt_provider')}/{config.get('stt_model')} "
        f"LLM={config.get('llm_provider')}/{config.get('llm_model')} "
        f"TTS={config.get('tts_provider')}/{config.get('tts_model')}"
    )

    await ctx.connect()

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


def main():
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
