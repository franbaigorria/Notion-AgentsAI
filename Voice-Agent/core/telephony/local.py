"""LocalTelephony — modo texto (stdin/stdout) para correr el agente sin Twilio.

Implementa TelephonyProvider para desarrollo local y tests.
Modo audio (sounddevice) diferido — no bloquea nada hoy.

Uso:
    python -m core.orchestrator.local --vertical clinica --mode text
"""

import asyncio
import sys
from collections.abc import AsyncIterator

from .base import TelephonyProvider


class LocalTelephony(TelephonyProvider):
    """Telephony provider de texto — stdin como entrada, stdout como salida."""

    def __init__(self, mode: str = "text"):
        if mode != "text":
            raise NotImplementedError(
                f"Modo '{mode}' no implementado. Solo 'text' disponible por ahora."
            )
        self.mode = mode

    async def receive_audio(self) -> AsyncIterator[bytes]:
        """No aplica en modo texto. Usar receive_text() en su lugar."""
        raise NotImplementedError("LocalTelephony modo texto no usa audio. Usar receive_text().")

    async def send_audio(self, audio: AsyncIterator[bytes]) -> None:
        """No aplica en modo texto. Usar send_text() en su lugar."""
        raise NotImplementedError("LocalTelephony modo texto no usa audio. Usar send_text().")

    def get_caller_id(self) -> str:
        return "local"

    async def receive_text(self) -> str | None:
        """Lee una línea de stdin. Retorna None en EOF (Ctrl+D / pipe vacío)."""
        loop = asyncio.get_event_loop()
        line = await loop.run_in_executor(None, sys.stdin.readline)
        return line.rstrip("\n") if line else None

    def send_text(self, text: str) -> None:
        """Escribe al stdout con flush inmediato para no perder output al pipear."""
        print(text, flush=True)
