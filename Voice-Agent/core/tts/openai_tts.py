"""Implementación de TTSProvider usando OpenAI TTS.

Modelos disponibles: gpt-4o-mini-tts (default), tts-1, tts-1-hd
Voces: alloy, ash, coral, echo, fable, onyx, nova, sage, shimmer

Uso en AgentSession (LiveKit Agents 1.x):
    tts = OpenAITTS(voice="nova")
    session = AgentSession(tts=tts.as_livekit_plugin(), ...)
"""

import os
from collections.abc import AsyncIterator

from livekit.plugins.openai import tts as lk_openai_tts

from .base import TTSProvider, TTSResult


class OpenAITTS(TTSProvider):
    def __init__(
        self,
        voice: str = "nova",
        model: str = "gpt-4o-mini-tts",
    ):
        self.voice = voice
        self.model = model

    def as_livekit_plugin(self) -> lk_openai_tts.TTS:
        return lk_openai_tts.TTS(
            api_key=os.environ["OPENAI_API_KEY"],
            voice=self.voice,
            model=self.model,
        )

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[bytes]:
        raise NotImplementedError("Usar as_livekit_plugin() para síntesis via LiveKit")

    def estimate_cost(self, text: str) -> TTSResult:
        # tts-1: $0.015/1K chars | gpt-4o-mini-tts: ~$0.006/1K chars
        cost_per_char = 0.000006
        return TTSResult(
            latency_ms=0,
            cost_usd=len(text) * cost_per_char,
            provider="openai_tts",
        )
