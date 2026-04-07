from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class STTResult:
    text: str
    latency_ms: float
    cost_usd: float


class STTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio: np.ndarray, sample_rate: int) -> STTResult: ...
