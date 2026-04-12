"""Orquestador principal — Voice Agent Platform.

Carga la configuracion del vertical y arranca un AgentSession de LiveKit.

Stack recomendado para produccion (sub-300ms E2E):
    LLM:  Groq (llama-3.1-8b-instant) — TTFT ~130ms
    STT:  Deepgram Nova-2
    TTS:  Deepgram Aura-2 (aura-2-antonia-es)

Uso:
    $env:VERTICAL="clinica"; python -m core.orchestrator.agent dev   # desarrollo
    python -m core.orchestrator.agent start                           # produccion

Variables de entorno requeridas:
    VERTICAL            nombre del directorio en verticals/ (default: clinica)
    LIVEKIT_URL         URL del servidor LiveKit
    LIVEKIT_API_KEY     API key de LiveKit
    LIVEKIT_API_SECRET  API secret de LiveKit
    DEEPGRAM_API_KEY    API key de Deepgram (STT + TTS)
    GROQ_API_KEY        API key de Groq (LLM rapido)
    ANTHROPIC_API_KEY   API key de Anthropic (LLM alternativo)
    ELEVENLABS_API_KEY  API key de ElevenLabs (TTS alternativo)
    OPENAI_API_KEY      API key de OpenAI (LLM/TTS alternativo)
"""

import os
from pathlib import Path
from typing import AsyncIterable, Any

from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, FlushSentinel, JobContext, ModelSettings, WorkerOptions, cli
from livekit.agents import llm as agents_llm
from livekit.agents.metrics import log_metrics
from livekit.plugins import silero

from core.orchestrator.config import load_vertical
# Plugin registration DEBE ocurrir en el main thread — NO mover estos imports a funciones
from core.stt.deepgram import DeepgramSTT  # noqa: F401
from core.tts.deepgram import DeepgramTTS  # noqa: F401
from core.tts.elevenlabs import ElevenLabsTTS  # noqa: F401
from core.tts.openai_tts import OpenAITTS  # noqa: F401
from core.llm.claude import ClaudeLLM  # noqa: F401
from core.llm.groq import GroqLLM  # noqa: F401

load_dotenv()

_VERTICALS_DIR = Path(__file__).parent.parent.parent / "verticals"


def _load_rag(vertical: str):
    """Carga el RAG si existe el directorio kb/. Retorna None si no hay KB."""
    kb_dir = _VERTICALS_DIR / vertical / "kb"
    if not kb_dir.exists() or not list(kb_dir.glob("*.md")):
        return None
    try:
        from core.rag.qdrant import QdrantRAG
        return QdrantRAG.from_kb_dir(kb_dir, vertical)
    except ImportError:
        return None


def build_stt(config: dict):
    providers = {
        "deepgram": lambda: DeepgramSTT(
            model=config.get("stt_model", "nova-2"),
            language=config.get("language", "es"),
        ),
    }
    name = config.get("stt_provider", "deepgram")
    if name not in providers:
        raise ValueError(f"STT provider desconocido: '{name}'. Disponibles: {list(providers)}")
    return providers[name]().as_livekit_plugin()


def build_llm(config: dict):
    providers = {
        "groq": lambda: GroqLLM(model=config.get("llm_model", "llama-3.1-8b-instant")),
        "claude": lambda: ClaudeLLM(model=config.get("llm_model", "claude-sonnet-4-6")),
    }
    name = config.get("llm_provider", "groq")
    if name not in providers:
        raise ValueError(f"LLM provider desconocido: '{name}'. Disponibles: {list(providers)}")
    return providers[name]().as_livekit_plugin()


def build_tts(config: dict):
    providers = {
        "deepgram": lambda: DeepgramTTS(
            model=config.get("tts_model", "aura-2-antonia-es"),
        ),
        "elevenlabs": lambda: ElevenLabsTTS(
            voice_id=config["voice_id"],
            model=config.get("tts_model", "eleven_multilingual_v2"),
        ),
        "openai": lambda: OpenAITTS(
            voice=config.get("tts_voice", "nova"),
            model=config.get("tts_model", "gpt-4o-mini-tts"),
        ),
    }
    name = config.get("tts_provider", "deepgram")
    if name not in providers:
        raise ValueError(f"TTS provider desconocido: '{name}'. Disponibles: {list(providers)}")
    return providers[name]().as_livekit_plugin()


class RAGAgent(Agent):
    """Agent con RAG — inyecta contexto de la KB en el system prompt antes de cada LLM call.

    Estrategia:
    - Por turno: busca contexto relevante para la pregunta actual
    - Caching: si el turno actual no trae contexto nuevo, mantiene el ultimo relevante
    Esto evita que Claude/Groq "olvide" informacion entre turnos de la misma conversacion.
    """

    def __init__(self, instructions: str, rag, vertical: str):
        super().__init__(instructions=instructions)
        self._rag = rag
        self._vertical = vertical
        self._base_instructions = instructions
        self._cached_rag_context: str | None = None

    def _build_augmented(self, context: str) -> str:
        return (
            self._base_instructions
            + "\n\n--- Informacion oficial (fuente autorizada) ---\n"
            "IMPORTANTE: Solo podes mencionar especialidades, medicos, horarios y precios "
            "que aparezcan EXACTAMENTE en este contexto. Si un dato no esta aqui, decis "
            "'no tengo ese dato disponible ahora'. NUNCA inventes ni supongas datos.\n\n"
            + context
            + "\n--- Fin de informacion oficial ---"
        )

    async def llm_node(
        self,
        chat_ctx: agents_llm.ChatContext,
        tools: list[agents_llm.Tool],
        model_settings: ModelSettings,
    ) -> AsyncIterable[agents_llm.ChatChunk | str | FlushSentinel] | Any:
        if self._rag:
            messages = chat_ctx.messages()
            user_messages = [m for m in messages if m.role == "user"]

            if user_messages:
                content = user_messages[-1].content
                last_user_text = (
                    content if isinstance(content, str)
                    else " ".join(c for c in content if isinstance(c, str))
                )

                if last_user_text.strip():
                    rag_result = await self._rag.retrieve(last_user_text, self._vertical)
                    if rag_result and rag_result.context:
                        self._cached_rag_context = rag_result.context

            if self._cached_rag_context:
                await self.update_instructions(self._build_augmented(self._cached_rag_context))

        return Agent.default.llm_node(self, chat_ctx, tools, model_settings)


async def entrypoint(ctx: JobContext) -> None:
    vertical_name = os.environ.get("VERTICAL", "clinica")
    config = load_vertical(vertical_name)
    rag = _load_rag(vertical_name)

    print(f"[Agent] Vertical: {vertical_name} | LLM: {config.get('llm_provider', 'groq')} | TTS: {config.get('tts_provider', 'deepgram')}")
    print(f"[RAG] {'KB cargada' if rag else 'Sin KB'} para vertical '{vertical_name}'")

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
        agent=RAGAgent(
            instructions=config["persona"],
            rag=rag,
            vertical=vertical_name,
        ),
        room=ctx.room,
    )

    await session.generate_reply(
        instructions=config.get(
            "greeting",
            "Saluda al usuario con calidez y preguntale en que podes ayudarlo.",
        )
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="clinica",
        )
    )
