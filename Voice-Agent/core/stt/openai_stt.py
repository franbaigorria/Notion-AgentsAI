"""Implementación de STTProvider usando OpenAI (gpt-4o-mini-transcribe).

Soporta dos modos:
  - use_realtime=True  → WebSocket streaming con resultados intermedios (vía LiveKit)
  - use_realtime=False → REST batch via openai SDK directo

Uso en AgentSession (LiveKit Agents 1.x):
    stt = OpenAISTT(model="gpt-4o-mini-transcribe", use_realtime=True)
    session = AgentSession(stt=stt.as_livekit_plugin(), ...)

Uso directo (sin LiveKit, solo use_realtime=False):
    stt = OpenAISTT(use_realtime=False)
    result = await stt.transcribe(audio_bytes, language="es")
"""

import time

from livekit.plugins import openai as lk_openai

from .base import STTProvider, STTResult

# Precio OpenAI gpt-4o-mini-transcribe: ~$0.006/min = $0.0001/sec
_COST_PER_SECOND_USD = 0.0001


class OpenAISTT(STTProvider):
    def __init__(
        self,
        model: str = "gpt-4o-mini-transcribe",
        language: str = "es",
        use_realtime: bool = True,
        api_key: str | None = None,
    ):
        self.model = model
        self.language = language
        self.use_realtime = use_realtime
        self.api_key = api_key

    def as_livekit_plugin(self) -> lk_openai.STT:
        """Retorna el plugin LiveKit para usar en AgentSession."""
        kwargs: dict = {
            "model": self.model,
            "language": self.language,
            "use_realtime": self.use_realtime,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        return lk_openai.STT(**kwargs)

    async def transcribe(self, audio: bytes, language: str) -> STTResult:
        """Transcripción directa via API de OpenAI (solo use_realtime=False).

        Para uso en AgentSession con streaming usar as_livekit_plugin() en su lugar.
        """
        if self.use_realtime:
            raise NotImplementedError(
                "transcribe() directo no está soportado con use_realtime=True. "
                "Usá as_livekit_plugin() para streaming en AgentSession."
            )

        import openai
        import os

        lang = language or self.language
        client = openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

        start = time.monotonic()
        result = await client.audio.transcriptions.create(
            model=self.model,
            file=audio,
            language=lang,
        )
        latency_ms = (time.monotonic() - start) * 1000

        # Estimación de duración: asume PCM 16kHz mono 16-bit
        duration_s = max(len(audio) / 32000, 1.0)

        return STTResult(
            transcript=result.text,
            confidence=1.0,
            latency_ms=latency_ms,
            cost_usd=duration_s * _COST_PER_SECOND_USD,
            provider="openai",
        )
