from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TTSResult:
    audio: bytes
    latency_ms: float
    cost_usd: float


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> TTSResult: ...
