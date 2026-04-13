import asyncio
import os
import subprocess
import tempfile
from typing import AsyncIterator

import numpy as np
import sounddevice as sd

from .base import TelephonyProvider

SAMPLE_RATE = 16_000
CHUNK = 1024
SILENCE_THRESHOLD = 500
SILENCE_CHUNKS = int(0.8 * SAMPLE_RATE / CHUNK)  # ~0.8 segundos de silencio


class LocalInput(TelephonyProvider):
    def get_caller_id(self) -> str:
        return "local-test"

    async def receive_text(self) -> AsyncIterator[str]:
        while True:
            try:
                text = await asyncio.to_thread(input, "\n> ")
                if text.strip():
                    yield text.strip()
            except (EOFError, asyncio.CancelledError):
                return

    async def record_audio(self) -> tuple[np.ndarray, int]:
        audio = await asyncio.to_thread(self._record_sync)
        return audio, SAMPLE_RATE

    def _record_sync(self) -> np.ndarray:
        input("\n[Enter para hablar]")
        print("🎤 Grabando... (silencio para parar)")
        chunks: list[np.ndarray] = []
        silent = 0

        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=CHUNK
        ) as stream:
            while True:
                data, _ = stream.read(CHUNK)
                chunks.append(data.copy())
                rms = np.abs(data).mean()
                if rms < SILENCE_THRESHOLD:
                    silent += 1
                    if silent >= SILENCE_CHUNKS:
                        break
                else:
                    silent = 0

        # descarta el silencio final
        useful = chunks[:-SILENCE_CHUNKS] if len(chunks) > SILENCE_CHUNKS else chunks
        return np.concatenate(useful).flatten()

    async def play_audio(self, audio: bytes) -> None:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio)
            tmp_path = f.name
        try:
            await asyncio.to_thread(
                subprocess.run, ["afplay", tmp_path], check=True
            )
        finally:
            os.unlink(tmp_path)
