"""Observability — tracing para direct-mode (RQ-03, RQ-04).

Instrumenta métodos async que retornan objetos con latency_ms / cost_usd.
Emite eventos JSON estructurados para correlacionar un turno completo.

Nota: solo instrumenta direct-mode. Instrumentar el pipeline LiveKit
requiere el event bus de LiveKit — Phase 3+.

Uso:
    from core.observability.tracing import track, current_call_id
    import uuid

    # Setear call_id al inicio de cada turno
    current_call_id.set(str(uuid.uuid4()))

    class MyLLM:
        @track(provider="claude", operation="complete")
        async def complete(self, ctx): ...

Configuración:
    OBSERVABILITY_SINK=stdout   (default) — imprime a stdout
    OBSERVABILITY_SINK=none     — desactiva
    OBSERVABILITY_SINK=file:/path/to/file.jsonl — escribe a archivo
"""

import functools
import json
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# ID compartido por todos los eventos de un mismo turno
current_call_id: ContextVar[str] = ContextVar("current_call_id", default="")

_SINK = os.environ.get("OBSERVABILITY_SINK", "none")


def _emit(event: dict) -> None:
    """Escribe el evento según el sink configurado."""
    if _SINK == "none":
        return

    line = json.dumps(event, ensure_ascii=False)

    if _SINK == "stdout":
        print(line, file=sys.stderr, flush=True)
    elif _SINK.startswith("file:"):
        path = _SINK[5:]
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def track(provider: str, operation: str):
    """Decorator para métodos async que retornan objetos con latency_ms y cost_usd.

    Emite un evento JSON por llamada:
    {
        "call_id": "...",
        "provider": "claude",
        "operation": "complete",
        "latency_ms": 342.1,
        "cost_usd": 0.00021,
        "timestamp": "2026-04-12T15:00:00Z"
    }
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            result = await fn(*args, **kwargs)

            latency_ms = getattr(result, "latency_ms", None)
            cost_usd = getattr(result, "cost_usd", None)

            event = {
                "call_id": current_call_id.get(),
                "provider": provider,
                "operation": operation,
                "latency_ms": latency_ms,
                "cost_usd": cost_usd,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            }
            _emit(event)

            return result

        return wrapper
    return decorator


def record_tts_stream(provider: str = "elevenlabs", operation: str = "synthesize"):
    """Wrapper para async generators (synthesize) — mide duración total al cerrar.

    No usa @functools.wraps porque los generators necesitan tratamiento especial.

    Uso:
        original_synthesize = tts.synthesize
        tts.synthesize = record_tts_stream()(original_synthesize)
    """
    import time

    def decorator(fn):
        async def wrapper(*args, **kwargs):
            start = time.monotonic()
            byte_count = 0

            async for chunk in await fn(*args, **kwargs):
                byte_count += len(chunk)
                yield chunk

            latency_ms = (time.monotonic() - start) * 1000
            text = args[1] if len(args) > 1 else kwargs.get("text", "")
            cost_usd = len(text) * 0.000030  # mismo precio que ElevenLabsTTS

            event = {
                "call_id": current_call_id.get(),
                "provider": provider,
                "operation": operation,
                "latency_ms": latency_ms,
                "cost_usd": cost_usd,
                "bytes_total": byte_count,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            }
            _emit(event)

        return wrapper
    return decorator
