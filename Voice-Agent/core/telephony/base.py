from abc import ABC, abstractmethod
from typing import AsyncIterator

import numpy as np


class TelephonyProvider(ABC):
    @abstractmethod
    def get_caller_id(self) -> str: ...

    @abstractmethod
    async def receive_text(self) -> AsyncIterator[str]: ...

    @abstractmethod
    async def play_audio(self, audio: bytes) -> None: ...

    async def record_audio(self) -> tuple[np.ndarray, int] | None:
        """Graba audio del micrófono. Retorna (audio, sample_rate) o None si no soportado."""
        return None
