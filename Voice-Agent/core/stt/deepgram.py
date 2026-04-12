"""Implementación de STTProvider usando Deepgram Nova-2.

Proveedor primario para español argentino — mejor precisión y latencia
que Whisper en español rioplatense según benchmarks internos.

Uso en AgentSession (LiveKit Agents 1.x):
    stt = DeepgramSTT(language="es")
    session = AgentSession(stt=stt.as_livekit_plugin(), ...)

Uso directo (sin LiveKit, para tests o futura migración):
    stt = DeepgramSTT(language="es")
    result = await stt.transcribe(audio_bytes, language="es")
"""

import time

from livekit.plugins import deepgram as lk_deepgram

from core.observability.tracing import track

from .base import STTProvider, STTResult

# Precio Deepgram Nova-2 al momento de implementación
_COST_PER_SECOND_USD = 0.0059 / 60


class DeepgramSTT(STTProvider):
    def __init__(self, model: str = "nova-2", language: str = "es"):
        self.model = model
        self.language = language

    def as_livekit_plugin(self) -> lk_deepgram.STT:
        """Retorna el plugin LiveKit para usar en AgentSession."""
        return lk_deepgram.STT(model=self.model, language=self.language)

    @track(provider="deepgram", operation="transcribe")
    async def transcribe(self, audio: bytes, language: str) -> STTResult:
        """Transcripción directa via API de Deepgram (sin LiveKit pipeline).

        Nota: requiere `deepgram-sdk` instalado. Para uso en AgentSession
        usar as_livekit_plugin() en su lugar.
        """
        try:
            from deepgram import DeepgramClient, PrerecordedOptions
        except ImportError as e:
            raise ImportError(
                "deepgram-sdk no instalado. Agregá 'deepgram-sdk' a las dependencias "
                "para transcripción directa. Para AgentSession usá as_livekit_plugin()."
            ) from e

        import os

        client = DeepgramClient(os.environ["DEEPGRAM_API_KEY"])
        options = PrerecordedOptions(model=self.model, language=language or self.language)

        start = time.monotonic()
        response = await client.listen.asyncrest.v("1").transcribe_raw(
            audio, options, timeout=30
        )
        latency_ms = (time.monotonic() - start) * 1000

        transcript = response.results.channels[0].alternatives[0].transcript
        confidence = response.results.channels[0].alternatives[0].confidence
        duration_s = response.metadata.duration

        return STTResult(
            transcript=transcript,
            confidence=confidence,
            latency_ms=latency_ms,
            cost_usd=duration_s * _COST_PER_SECOND_USD,
            provider="deepgram",
        )
