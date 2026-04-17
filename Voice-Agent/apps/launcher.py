"""Launcher — Despacha al agente correcto según AGENT_MODE.

Railway ejecuta siempre este módulo. La env var AGENT_MODE decide
qué arquitectura se levanta:

    AGENT_MODE=pipeline  → STT (Deepgram) → LLM (OpenAI) → TTS (ElevenLabs)
    AGENT_MODE=realtime  → OpenAI speech-to-speech (gpt-4o-mini-realtime)

Default: pipeline (la opción con voz custom argentina).

Uso:
    uv run python -m apps.launcher start       # producción
    uv run python -m apps.launcher dev         # desarrollo local
"""

import os
import sys


def main():
    mode = os.environ.get("AGENT_MODE", "pipeline").lower().strip()

    if mode == "realtime":
        print("[LAUNCHER] Arrancando en modo: realtime")
        from apps.realtime.agent import main as run
    elif mode == "pipeline":
        print("[LAUNCHER] Arrancando en modo: pipeline")
        from apps.pipeline.agent import main as run
    else:
        print(
            f"[LAUNCHER] AGENT_MODE='{mode}' no es válido. "
            f"Opciones: pipeline | realtime",
            file=sys.stderr,
        )
        sys.exit(1)

    run()


if __name__ == "__main__":
    main()
