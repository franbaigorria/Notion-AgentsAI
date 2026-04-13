"""Implementación de TTSProvider usando ElevenLabs.

Proveedor primario por naturalidad en español rioplatense.
Soporta VoiceSettings para tuning fino de estabilidad, estilo y velocidad.

Uso en AgentSession (LiveKit Agents 1.x):
    tts = ElevenLabsTTS(voice_id="...", model="eleven_flash_v2_5")
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
        stability: float | None = None,
        similarity_boost: float | None = None,
        style: float | None = None,
        speed: float | None = None,
        apply_text_normalization: str = "auto",
    ):
        self.voice_id = voice_id
        self.model = model
        self.stability = stability
        self.similarity_boost = similarity_boost
        self.style = style
        self.speed = speed
        self.apply_text_normalization = apply_text_normalization

    def _build_voice_settings(self) -> lk_elevenlabs.VoiceSettings | None:
        if self.stability is None and self.similarity_boost is None:
            return None
        return lk_elevenlabs.VoiceSettings(
            stability=self.stability or 0.5,
            similarity_boost=self.similarity_boost or 0.75,
            style=self.style,
            speed=self.speed,
        )

    def as_livekit_plugin(self) -> lk_elevenlabs.TTS:
        """Retorna el plugin LiveKit para usar en AgentSession."""
        voice_settings = self._build_voice_settings()
        kwargs: dict = {
            "api_key": os.environ["ELEVENLABS_API_KEY"],
            "voice_id": self.voice_id,
            "model": self.model,
            "apply_text_normalization": self.apply_text_normalization,
        }
        if voice_settings is not None:
            kwargs["voice_settings"] = voice_settings
        return lk_elevenlabs.TTS(**kwargs)

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
