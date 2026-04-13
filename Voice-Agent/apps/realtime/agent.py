"""Realtime Agent — OpenAI Speech-to-Speech.

Un único modelo (gpt-4o-mini-realtime) que reemplaza STT + LLM + TTS.
No requiere VAD, STT ni TTS — todo corre dentro del WebSocket de OpenAI.

Uso directo (dev):
    AGENT_MODE=realtime uv run python -m apps.realtime.agent dev

En producción se levanta via apps.launcher.
"""

import os

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.agents.metrics import log_metrics

from core.orchestrator.agent import build_realtime_llm, load_vertical


async def entrypoint(ctx: JobContext) -> None:
    vertical_name = os.environ.get("VERTICAL", "clinica")
    config = load_vertical(vertical_name)

    rt = config.get("realtime", {})
    print(f"[MODE=realtime] model={rt.get('model')} voice={rt.get('voice')}")

    await ctx.connect()

    session = AgentSession(llm=build_realtime_llm(config))

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
