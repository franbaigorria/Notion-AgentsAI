"""Implementación de TTSProvider usando Deepgram Aura.

Alternativa a ElevenLabs con streaming via WebSocket y voz argentina disponible.
El modelo incluye la voz — no hay voice_id separado como en ElevenLabs.

Voces en español disponibles:
    aura-2-antonia-es  — argentina (feminina)    ← usada por defecto
    aura-2-sirio-es    — mexicana (masculina)
    aura-2-javier-es   — mexicana (masculina)
    aura-2-gloria-es   — colombiana (feminina)
    aura-2-carina-es   — peninsular (feminina)

Uso en AgentSession (LiveKit Agents 1.x):
    tts = DeepgramTTS(model="aura-2-antonia-es")
    session = AgentSession(tts=tts.as_livekit_plugin(), ...)

Uso directo (sin LiveKit):
    tts = DeepgramTTS(model="aura-2-antonia-es")
    async for chunk in tts.synthesize(text, voice_id=""):
        ...
"""

import os
from collections.abc import AsyncIterator

from livekit.plugins import deepgram as lk_deepgram

from .base import TTSProvider, TTSResult, _make_preprocessed_tts, strip_tone_tags

_DEEPGRAM_SPEAK_URL = "https://api.deepgram.com/v1/speak"

# Precio Deepgram Aura-2 por caracter (USD)
_COST_PER_CHAR_USD = 0.000015  # $0.015 per 1,000 chars


class DeepgramTTS(TTSProvider):
    """TTS via Deepgram Aura-2 — streaming WebSocket en LiveKit, REST para uso directo.

    En Deepgram el nombre del modelo lleva embebida la voz y el idioma,
    por eso no existe un voice_id separado. En synthesize(), voice_id actúa
    como override del modelo si se provee; si no, usa self.model.
    """

    def __init__(
        self,
        model: str = "aura-2-antonia-es",
        encoding: str = "linear16",
        sample_rate: int = 24000,
    ):
        self.model = model
        self.encoding = encoding
        self.sample_rate = sample_rate

    def as_livekit_plugin(self):
        """Retorna el plugin LiveKit para usar en AgentSession.

        Envuelto con _make_preprocessed_tts para eliminar <tone:X> antes
        de que lleguen a la API de Deepgram.
        """
        plugin = lk_deepgram.TTS(
            model=self.model,
            encoding=self.encoding,
            sample_rate=self.sample_rate,
            api_key=os.environ["DEEPGRAM_API_KEY"],
        )
        return _make_preprocessed_tts(plugin, strip_tone_tags)

    async def synthesize(self, text: str, voice_id: str = "") -> AsyncIterator[bytes]:
        """Síntesis directa via REST API de Deepgram como stream de bytes.

        Args:
            text:     Texto a sintetizar.
            voice_id: Nombre del modelo Deepgram Aura (ej: "aura-2-antonia-es").
                      Si está vacío, usa self.model configurado en __init__.
        """
        import aiohttp

        model = voice_id if voice_id else self.model
        url = (
            f"{_DEEPGRAM_SPEAK_URL}"
            f"?model={model}"
            f"&encoding={self.encoding}"
            f"&sample_rate={self.sample_rate}"
        )
        headers = {
            "Authorization": f"Token {os.environ['DEEPGRAM_API_KEY']}",
            "Content-Type": "application/json",
        }

        async def _stream() -> AsyncIterator[bytes]:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"text": text},
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    async for chunk in response.content.iter_chunked(4096):
                        yield chunk

        return _stream()

    def estimate_cost(self, text: str) -> TTSResult:
        return TTSResult(
            latency_ms=0,
            cost_usd=len(text) * _COST_PER_CHAR_USD,
            provider="deepgram_aura",
        )
