"""Implementación de TTSProvider usando OpenAI TTS (gpt-4o-mini-tts).

Modelo con billing por token — más eficiente para textos cortos.
Soporta `instructions` para control de tono a nivel de sesión.

Uso en AgentSession (LiveKit Agents 1.x):
    tts = OpenAITTS(voice="ash", instructions="Respondé con calidez y brevedad.")
    session = AgentSession(tts=tts.as_livekit_plugin(), ...)

Uso directo (sin LiveKit):
    tts = OpenAITTS(voice="ash")
    async for chunk in await tts.synthesize(text, ""):
        ...
"""

import os
from collections.abc import AsyncIterator

from livekit.plugins import openai as lk_openai

from .base import TTSProvider, TTSResult, _make_preprocessed_tts, strip_tone_tags

# Precio por output token — gpt-4o-mini-tts (token-billed, ~$2.40/1M tokens)
_COST_PER_TOKEN_USD = 0.0000024


class OpenAITTS(TTSProvider):
    def __init__(
        self,
        voice: str = "ash",
        model: str = "gpt-4o-mini-tts",
        instructions: str | None = None,
        speed: float = 1.0,
        api_key: str | None = None,
    ):
        self.voice = voice
        self.model = model
        self.instructions = instructions
        self.speed = speed
        self.api_key = api_key

    def as_livekit_plugin(self):
        """Retorna el plugin LiveKit para usar en AgentSession.

        Envuelto con _make_preprocessed_tts para eliminar <tone:X> antes
        de que lleguen a la API de OpenAI TTS.
        """
        kwargs: dict = {
            "voice": self.voice,
            "model": self.model,
            "speed": self.speed,
        }
        if self.instructions is not None:
            kwargs["instructions"] = self.instructions
        if self.api_key:
            kwargs["api_key"] = self.api_key
        plugin = lk_openai.TTS(**kwargs)
        return _make_preprocessed_tts(plugin, strip_tone_tags)

    async def synthesize(self, text: str, voice_id: str = "") -> AsyncIterator[bytes]:
        """Síntesis directa via API de OpenAI como stream de bytes."""
        import openai

        client = openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        clean_text = strip_tone_tags(text)
        response = await client.audio.speech.create(
            model=self.model,
            voice=self.voice,
            input=clean_text,
        )

        async def _stream() -> AsyncIterator[bytes]:
            async for chunk in response.aiter_bytes():
                yield chunk

        return _stream()

    def estimate_cost(self, text: str) -> TTSResult:
        tokens = len(text) * 0.25  # ~0.25 tokens/char para texto en español
        return TTSResult(
            latency_ms=0,
            cost_usd=tokens * _COST_PER_TOKEN_USD,
            provider="openai",
        )
