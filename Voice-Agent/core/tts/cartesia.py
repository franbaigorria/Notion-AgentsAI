"""Implementación de TTSProvider usando Cartesia.

Provee un TTS extremadamente rápido diseñado para voz en tiempo real.
"""

import os
from collections.abc import AsyncIterator

from livekit.plugins import cartesia as lk_cartesia

from .base import TTSProvider, TTSResult

# Pricing aproximado de Cartesia (por caracter)
_COST_PER_CHAR_USD = 0.00001


class CartesiaTTS(TTSProvider):
    """TTS via Cartesia Sonic — streaming WebSocket en LiveKit."""

    def __init__(self, voice_id: str, model: str = "sonic-multilingual"):
        self.voice_id = voice_id
        self.model = model

    def as_livekit_plugin(self) -> lk_cartesia.TTS:
        """Retorna el plugin LiveKit configurado para Cartesia."""
        api_key = os.environ.get("CARTESIA_API_KEY")
        if not api_key:
            raise ValueError("CARTESIA_API_KEY no está configurada")

        return lk_cartesia.TTS(
            voice=self.voice_id,
            model=self.model,
            api_key=api_key,
        )

    async def synthesize(self, text: str, voice_id: str = "") -> AsyncIterator[bytes]:
        """Cartesia REST stream. Implementado como stub para uso directo."""
        # En una integración completa, aquí iría la llamada HTTP de Cartesia
        raise NotImplementedError("REST/Direct synthesize para Cartesia no está implementado")

    def estimate_cost(self, text: str) -> TTSResult:
        return TTSResult(
            latency_ms=0,
            cost_usd=len(text) * _COST_PER_CHAR_USD,
            provider="cartesia",
        )
