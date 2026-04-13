"""Implementación speech-to-speech usando OpenAI Realtime API.

A diferencia del pipeline STT→LLM→TTS, Realtime maneja audio en ambas direcciones
directamente. Se reemplaza TODO el pipeline con un único modelo.

Uso en AgentSession (LiveKit Agents 1.x):
    realtime = OpenAIRealtime(model="gpt-4o-mini-realtime-preview", voice="ash")
    session = AgentSession(llm=realtime.as_livekit_plugin())

NO se pasan stt, tts ni vad — Realtime los reemplaza.

Voces disponibles (todas de OpenAI, ninguna nativa argentina):
    - alloy     neutra
    - echo      masculina
    - shimmer   femenina
    - ash       masculina (recomendada para recepcionista)
    - ballad    masculina, lírica
    - coral     femenina
    - sage      femenina, suave
    - verse     masculina, expresiva
"""

import os

from livekit.plugins.openai import realtime as lk_realtime


class OpenAIRealtime:
    """Adapter para OpenAI Realtime API — reemplaza STT + LLM + TTS."""

    def __init__(
        self,
        model: str = "gpt-4o-mini-realtime-preview",
        voice: str = "ash",
        temperature: float | None = None,
        speed: float | None = None,
    ):
        self.model = model
        self.voice = voice
        self.temperature = temperature
        self.speed = speed

    def as_livekit_plugin(self) -> lk_realtime.RealtimeModel:
        """Retorna el plugin LiveKit para usar en AgentSession."""
        kwargs: dict = {
            "api_key": os.environ["OPENAI_API_KEY"],
            "model": self.model,
            "voice": self.voice,
        }
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.speed is not None:
            kwargs["speed"] = self.speed
        return lk_realtime.RealtimeModel(**kwargs)
