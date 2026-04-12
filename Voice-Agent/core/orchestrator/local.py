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

from dotenv import load_dotenv

load_dotenv()

from core.llm.base import LLMContext, Message
from core.llm.claude import ClaudeLLM
from core.observability.tracing import current_call_id
from core.orchestrator.config import load_vertical
from core.telephony.local import LocalTelephony

_HISTORY_CAP = 20


async def run_local(vertical: str = "clinica", mode: str = "text") -> None:
    """Loop principal del modo local.

    Primer turno: genera el saludo usando el greeting del config.
    Turnos siguientes: responde al input del usuario.
    History cappeado a 20 mensajes — memoria persistente viene en Phase 4.
    """
    config = load_vertical(vertical)
    telephony = LocalTelephony(mode=mode)
    llm = ClaudeLLM(model=config.get("llm_model", "claude-sonnet-4-6"))

    system_prompt = config["persona"]
    history: list[Message] = []

    # Primer turno: saludo
    current_call_id.set(str(uuid.uuid4()))
    greeting_instruction = config.get(
        "greeting",
        "Saludá al usuario con calidez y preguntale en qué podés ayudarlo.",
    )
    greeting_ctx = LLMContext(
        system=system_prompt,
        messages=[Message(role="user", content=greeting_instruction)],
    )
    result = await llm.complete(greeting_ctx)
    telephony.send_text(result.content)
    history.append(Message(role="assistant", content=result.content))

    # Loop principal
    while True:
        user_input = await telephony.receive_text()

        # EOF (Ctrl+D o pipe vacío)
        if user_input is None:
            break

        # Comandos de salida
        if user_input.strip().lower() in {"exit", "quit", "salir", "chau"}:
            break

        # Input vacío — ignorar
        if not user_input.strip():
            continue

        history.append(Message(role="user", content=user_input))
        current_call_id.set(str(uuid.uuid4()))

        # Cap antes de enviar al LLM
        if len(history) > _HISTORY_CAP:
            history = history[-_HISTORY_CAP:]

        ctx = LLMContext(system=system_prompt, messages=history)
        result = await llm.complete(ctx)

        telephony.send_text(result.content)
        history.append(Message(role="assistant", content=result.content))

        # Cap después de agregar la respuesta
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
