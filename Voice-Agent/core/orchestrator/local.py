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

from core.flows.engine import FlowEngine
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


def _build_system(
    base: str,
    rag_result: RAGResult | None = None,
    flow_context: str | None = None,
    flow_guidance: str | None = None,
) -> str:
    """Augmenta el system prompt con contexto RAG, flow context y guía de flow.

    - rag_result: contexto por turno (pregunta específica del usuario)
    - flow_context: contexto del tema del flow, recuperado al activarse y persistente
    - flow_guidance: instrucciones de los pasos del flow
    """
    system = base

    # Combinar contextos — flow_context primero (tema general del flow),
    # rag_result después (pregunta específica del turno)
    combined_context = "\n\n---\n\n".join(filter(None, [
        flow_context,
        rag_result.context if rag_result and rag_result.context else None,
    ]))

    if combined_context:
        system += (
            "\n\n--- Información oficial de la clínica (fuente autorizada) ---\n"
            "Usá esta información para responder. Es oficial y verificada. "
            "Compartí números de teléfono, precios y horarios exactamente como aparecen acá.\n\n"
            f"{combined_context}\n"
            "--- Fin de información oficial ---"
        )

    if flow_guidance:
        system += f"\n\n{flow_guidance}"

    return system


def _build_rag_query(user_input: str, history: list, flow_name: str | None = None) -> str:
    """Enriquece la query al RAG con contexto de la conversación y el flow activo.

    - Queries cortas/pronominales: se enriquecen con los últimos turnos
    - Flow activo: se agrega el nombre del flow para que el RAG siempre
      traiga contexto relevante aunque el usuario esté hablando de otra cosa
      (ej: dando su DNI mientras el flow necesita los horarios de una especialidad)
    """
    # Contexto del flow como señal semántica
    flow_context = flow_name.replace("_", " ") if flow_name else ""

    if len(user_input.strip()) > 20:
        return f"{flow_context} {user_input}".strip() if flow_context else user_input

    # Input corto — agregar los últimos turnos como contexto
    recent = history[-4:] if len(history) >= 4 else history
    context_text = " ".join(m.content for m in recent)
    return f"{flow_context} {context_text} {user_input}".strip()


def _load_flows(vertical: str) -> FlowEngine | None:
    """Carga el FlowEngine si existe flows.yaml para el vertical."""
    path = _VERTICALS_DIR / vertical / "flows.yaml"
    if not path.exists():
        return None
    return FlowEngine.load(path)


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

    # Flows
    flow_engine = _load_flows(vertical)

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

        # Detectar flow si no hay uno activo
        if flow_engine and not flow_engine.active:
            detected = flow_engine.detect(user_input)
            if detected:
                flow_engine.activate(detected)
                # Recuperar contexto del tema del flow UNA VEZ al activarlo
                if rag:
                    flow_rag_query = flow_engine.get_flow_rag_query(detected)
                    flow_rag = await rag.retrieve(flow_rag_query, vertical, score_threshold=0.10)
                    flow_engine.flow_context = flow_rag.context if flow_rag else None

        # Buscar contexto por turno (pregunta específica del usuario)
        rag_query = _build_rag_query(user_input, history)
        rag_result = await rag.retrieve(rag_query, vertical) if rag else None

        flow_guidance = flow_engine.get_guidance() if flow_engine else None
        flow_context = flow_engine.flow_context if flow_engine else None
        system = _build_system(base_system, rag_result, flow_context, flow_guidance)

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
