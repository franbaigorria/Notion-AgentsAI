"""Entrypoint local — Voice Agent Platform sin LiveKit ni Twilio.

Loop: stdin → LLMContext (persona + history, cap 20) → ClaudeLLM.complete() → stdout.
Paralelo a entrypoint() en agent.py — no toca AgentSession.

Uso:
    python -m core.orchestrator.local --vertical clinica --mode text

    # O con pipe:
    echo "Quiero un turno para mañana" | python -m core.orchestrator.local --vertical clinica

Variables de entorno requeridas:
    ANTHROPIC_API_KEY  API key de Anthropic
"""

import asyncio
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from core.llm.base import LLMContext, Message
from core.llm.claude import ClaudeLLM
from core.observability.tracing import current_call_id
from core.orchestrator.config import load_vertical
from core.rag.base import RAGResult
from core.telephony.local import LocalTelephony

_HISTORY_CAP = 20
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
        print("[RAG] qdrant-client no instalado. Correr: pip install 'qdrant-client[fastembed]'")
        return None


def _build_system(base: str, rag_result: RAGResult | None) -> str:
    """Augmenta el system prompt con contexto del RAG si hay resultado relevante."""
    if not rag_result or not rag_result.context:
        return base
    return (
        f"{base}\n\n"
        "--- Información oficial de la clínica (fuente autorizada) ---\n"
        "Usá esta información para responder. Es oficial y verificada. "
        "Compartí números de teléfono, precios y horarios exactamente como aparecen acá.\n\n"
        f"{rag_result.context}\n"
        "--- Fin de información oficial ---"
    )


def _build_rag_query(user_input: str, history: list) -> str:
    """Enriquece la query al RAG con contexto de la conversación.

    Queries cortas o pronominales ("damelo", "sí", "dale") no matchean nada
    sin contexto. Usamos los últimos 2 turnos para dar señal semántica al RAG.
    """
    if len(user_input.strip()) > 20:
        return user_input

    # Input corto — agregar los últimos turnos como contexto
    recent = history[-4:] if len(history) >= 4 else history
    context_text = " ".join(m.content for m in recent)
    return f"{context_text} {user_input}".strip()


async def run_local(vertical: str = "clinica", mode: str = "text", rag=None) -> None:
    """Loop principal del modo local.

    Primer turno: genera el saludo usando el greeting del config.
    Turnos siguientes: busca contexto en RAG e inyecta en el system prompt antes de llamar al LLM.
    History cappeado a 20 mensajes — memoria persistente viene en Phase 4.
    """
    config = load_vertical(vertical)
    telephony = LocalTelephony(mode=mode)
    llm = ClaudeLLM(model=config.get("llm_model", "claude-sonnet-4-6"))

    # RAG: carga si no viene inyectado (permite override en tests)
    if rag is None:
        rag = _load_rag(vertical)

    base_system = config["persona"]
    history: list[Message] = []

    # Primer turno: saludo (sin RAG — el usuario no preguntó nada todavía)
    current_call_id.set(str(uuid.uuid4()))
    greeting_instruction = config.get(
        "greeting",
        "Saludá al usuario con calidez y preguntale en qué podés ayudarlo.",
    )
    greeting_ctx = LLMContext(
        system=base_system,
        messages=[Message(role="user", content=greeting_instruction)],
    )
    result = await llm.complete(greeting_ctx)
    telephony.send_text(result.content)
    history.append(Message(role="assistant", content=result.content))

    # Loop principal
    while True:
        user_input = await telephony.receive_text()

        if user_input is None:
            break
        if user_input.strip().lower() in {"exit", "quit", "salir", "chau"}:
            break
        if not user_input.strip():
            continue

        history.append(Message(role="user", content=user_input))
        current_call_id.set(str(uuid.uuid4()))

        if len(history) > _HISTORY_CAP:
            history = history[-_HISTORY_CAP:]

        # Buscar contexto relevante en la KB
        rag_query = _build_rag_query(user_input, history)
        rag_result = await rag.retrieve(rag_query, vertical) if rag else None
        system = _build_system(base_system, rag_result)

        ctx = LLMContext(system=system, messages=history)
        result = await llm.complete(ctx)

        telephony.send_text(result.content)
        history.append(Message(role="assistant", content=result.content))

        if len(history) > _HISTORY_CAP:
            history = history[-_HISTORY_CAP:]


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Voice Agent — modo local (sin LiveKit)")
    parser.add_argument("--vertical", default="clinica", help="Vertical a cargar (default: clinica)")
    parser.add_argument(
        "--mode",
        default="text",
        choices=["text"],
        help="Modo de E/S (default: text). Audio diferido.",
    )
    args = parser.parse_args()

    asyncio.run(run_local(vertical=args.vertical, mode=args.mode))


if __name__ == "__main__":
    main()
