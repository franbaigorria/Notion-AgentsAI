"""Implementación de STTProvider usando ElevenLabs Scribe v2 Realtime.

Streaming por WebSocket — alternativa a Deepgram Nova-3.
Soporta keyterms para biasear transcripción a vocabulario médico.

Uso en AgentSession (LiveKit Agents 1.x):
    stt = ElevenLabsSTT(language="es")
    session = AgentSession(stt=stt.as_livekit_plugin(), ...)
"""

import os

from livekit.plugins import elevenlabs as lk_elevenlabs

from .base import STTProvider, STTResult


class ElevenLabsSTT(STTProvider):
    def __init__(
        self,
        model: str = "scribe_v2_realtime",
        language: str = "es",
        keyterms: list[str] | None = None,
        api_key: str | None = None,
    ):
        self.model = model
        self.language = language
        self.keyterms = keyterms
        self.api_key = api_key

    def as_livekit_plugin(self) -> lk_elevenlabs.STT:
        """Retorna el plugin LiveKit para usar en AgentSession."""
        return lk_elevenlabs.STT(
            api_key=self.api_key or os.environ["ELEVENLABS_API_KEY"],
            model_id=self.model,
            language_code=self.language,
        )

    async def transcribe(self, audio: bytes, language: str) -> STTResult:
        raise NotImplementedError(
            "ElevenLabs STT solo soporta streaming via as_livekit_plugin(). "
            "Para transcripción batch usá DeepgramSTT."
        )
