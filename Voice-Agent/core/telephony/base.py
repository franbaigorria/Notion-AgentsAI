from abc import ABC, abstractmethod
from typing import AsyncIterator


class TelephonyProvider(ABC):
    @abstractmethod
    def get_caller_id(self) -> str: ...

    @abstractmethod
    async def receive_text(self) -> AsyncIterator[str]: ...

    @abstractmethod
    async def play_audio(self, audio: bytes) -> None: ...
