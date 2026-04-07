import asyncio
import os
import subprocess
import tempfile
from typing import AsyncIterator

from .base import TelephonyProvider


class LocalInput(TelephonyProvider):
    def get_caller_id(self) -> str:
        return "local-test"

    async def receive_text(self) -> AsyncIterator[str]:
        while True:
            try:
                text = await asyncio.to_thread(input, "\n> ")
                if text.strip():
                    yield text.strip()
            except EOFError:
                break

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
