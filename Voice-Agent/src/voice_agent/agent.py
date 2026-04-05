"""
Agente de voz para clínicas — LiveKit Agents 1.x

Stack:
  VAD:  Silero
  STT:  Deepgram (Nova-2, español)
  LLM:  Claude (claude-sonnet-4-6)
  TTS:  ElevenLabs

Ejecutar:
  python -m voice_agent.agent dev
"""

from dotenv import load_dotenv

load_dotenv()

import os

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import anthropic, deepgram, elevenlabs, silero

SYSTEM_PROMPT = """\
Sos Nanci, la asistente virtual de la clínica. Hablás en español rioplatense, \
de forma cálida y profesional.

Reglas:
- Respondé siempre en español argentino (vos, che, dale, etc.)
- Sé concisa: el paciente está al teléfono, no leyendo texto
- Nunca uses bullets, markdown ni listas — solo frases cortas y naturales
- Si no sabés algo, decilo con claridad y ofrecé derivar a alguien del equipo
- Si es una emergencia médica, derivá de inmediato al 107 o al médico de guardia
"""


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(
            model="nova-2",
            language="es",
        ),
        llm=anthropic.LLM(
            model="claude-sonnet-4-6",
        ),
        tts=elevenlabs.TTS(
            api_key=os.environ["ELEVENLABS_API_KEY"],
            voice_id="07BApwwAuIPJ9y3d8YQo",
            model="eleven_multilingual_v2",
        ),
    )

    await session.start(
        agent=Agent(instructions=SYSTEM_PROMPT),
        room=ctx.room,
    )

    await session.generate_reply(
        instructions="Saludá al paciente con calidez y preguntale en qué podés ayudarlo."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
