import io
import time
import wave

import numpy as np
from deepgram import AsyncDeepgramClient

from .base import STTProvider, STTResult

# Nova-2 pricing: $0.0043 / minuto de audio
COST_PER_MINUTE = 0.0043


class DeepgramSTT(STTProvider):
    def __init__(self, api_key: str, language: str = "es"):
        self.client = AsyncDeepgramClient(api_key=api_key)
        self.language = language

    async def transcribe(self, audio: np.ndarray, sample_rate: int) -> STTResult:
        start = time.perf_counter()
        wav_bytes = self._to_wav(audio, sample_rate)

        response = await self.client.listen.v1.media.transcribe_file(
            request=wav_bytes,
            model="nova-2",
            language=self.language,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        text = response.results.channels[0].alternatives[0].transcript
        duration_min = len(audio) / sample_rate / 60
        cost = duration_min * COST_PER_MINUTE

        return STTResult(text=text, latency_ms=latency_ms, cost_usd=cost)

    def _to_wav(self, audio: np.ndarray, sample_rate: int) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)  # int16 = 2 bytes
            f.setframerate(sample_rate)
            f.writeframes(audio.tobytes())
        return buf.getvalue()
