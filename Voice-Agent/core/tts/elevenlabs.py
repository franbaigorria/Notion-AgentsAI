"""Implementación de TTSProvider usando ElevenLabs.

Proveedor primario por naturalidad en español rioplatense.
Usa eleven_flash_v2_5 — mejor balance latencia/calidad para conversacional.

Uso en AgentSession (LiveKit Agents 1.x):
    tts = ElevenLabsTTS(voice_id="...")
    session = AgentSession(tts=tts.as_livekit_plugin(), ...)

Uso directo (sin LiveKit):
    tts = ElevenLabsTTS(voice_id="...")
    async for chunk in tts.synthesize(text, voice_id):
        ...
"""

import os
from collections.abc import AsyncIterator

from livekit.plugins import elevenlabs as lk_elevenlabs

from .base import TTSProvider, TTSResult

# Precio ElevenLabs por carácter (plan Creator)
_COST_PER_CHAR_USD = 0.000030


class ElevenLabsTTS(TTSProvider):
    def __init__(
        self,
        voice_id: str,
        model: str = "eleven_flash_v2_5",
    ):
        self.voice_id = voice_id
        self.model = model

    def as_livekit_plugin(self) -> lk_elevenlabs.TTS:
        """Retorna el plugin LiveKit para usar en AgentSession."""
        return lk_elevenlabs.TTS(
            api_key=os.environ["ELEVENLABS_API_KEY"],
            voice_id=self.voice_id,
            model=self.model,
        )

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[bytes]:
        """Síntesis directa via API de ElevenLabs como stream de bytes."""
        import time

        from elevenlabs.client import AsyncElevenLabs

        client = AsyncElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
        start = time.monotonic()

        async def _stream() -> AsyncIterator[bytes]:
            async for chunk in await client.text_to_speech.convert(
                voice_id=voice_id or self.voice_id,
                text=text,
                model_id=self.model,
                output_format="mp3_44100_128",
            ):
                yield chunk

        return _stream()

    def estimate_cost(self, text: str) -> TTSResult:
        return TTSResult(
            latency_ms=0,
            cost_usd=len(text) * _COST_PER_CHAR_USD,
            provider="elevenlabs",
        )
