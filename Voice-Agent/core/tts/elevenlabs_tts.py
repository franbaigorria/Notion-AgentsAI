import asyncio
import time

from elevenlabs import ElevenLabs

from .base import TTSProvider, TTSResult

# ElevenLabs pricing (~USD por 1k caracteres)
COST_PER_1K_CHARS = 0.0030


class ElevenLabsTTS(TTSProvider):
    def __init__(self, api_key: str, voice_id: str, model: str = "eleven_turbo_v2_5"):
        self.client = ElevenLabs(api_key=api_key)
        self.voice_id = voice_id
        self.model = model

    async def synthesize(self, text: str) -> TTSResult:
        start = time.perf_counter()
        audio_bytes = await asyncio.to_thread(self._synthesize_sync, text)
        latency_ms = (time.perf_counter() - start) * 1000
        cost = len(text) / 1000 * COST_PER_1K_CHARS

        return TTSResult(audio=audio_bytes, latency_ms=latency_ms, cost_usd=cost)

    def _synthesize_sync(self, text: str) -> bytes:
        chunks = self.client.text_to_speech.convert(
            voice_id=self.voice_id,
            text=text,
            model_id=self.model,
        )
        return b"".join(chunks)
