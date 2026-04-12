"""Providers falsos para tests — respuestas canned, sin llamadas reales a APIs.

Uso:
    from tests.fakes import FakeLLMProvider, FakeSTTProvider, FakeTTSProvider
"""

from collections.abc import AsyncIterator

from core.llm.base import LLMContext, LLMProvider, LLMResult
from core.stt.base import STTProvider, STTResult
from core.tts.base import TTSProvider, TTSResult


class FakeLLMProvider(LLMProvider):
    """LLM que siempre responde con texto fijo. Registra cada llamada en .calls."""

    def __init__(self, response: str = "Respuesta de prueba."):
        self.response = response
        self.calls: list[LLMContext] = []

    async def complete(self, context: LLMContext) -> LLMResult:
        self.calls.append(context)
        return LLMResult(
            content=self.response,
            input_tokens=10,
            output_tokens=5,
            latency_ms=1.0,
            cost_usd=0.0001,
            provider="fake",
        )

    async def stream(self, context: LLMContext) -> AsyncIterator[str]:
        self.calls.append(context)
        for word in self.response.split():
            yield word + " "

    async def optimize_for_tts(self, text: str) -> LLMResult:
        return LLMResult(
            content=text,
            input_tokens=5,
            output_tokens=5,
            latency_ms=1.0,
            cost_usd=0.0001,
            provider="fake",
        )


class FakeSTTProvider(STTProvider):
    """STT que siempre transcribe a texto fijo."""

    def __init__(self, transcript: str = "Quiero un turno para mañana."):
        self.transcript = transcript
        self.calls: list[bytes] = []

    async def transcribe(self, audio: bytes, language: str) -> STTResult:
        self.calls.append(audio)
        return STTResult(
            transcript=self.transcript,
            confidence=0.99,
            latency_ms=50.0,
            cost_usd=0.0001,
            provider="fake",
        )


class FakeTTSProvider(TTSProvider):
    """TTS que retorna bytes vacíos — solo verifica que se llame correctamente."""

    def __init__(self):
        self.calls: list[str] = []

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[bytes]:
        self.calls.append(text)

        async def _empty():
            yield b""

        return _empty()

    def estimate_cost(self, text: str) -> TTSResult:
        return TTSResult(latency_ms=0, cost_usd=0.0, provider="fake")
