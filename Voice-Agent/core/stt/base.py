from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class STTResult:
    transcript: str
    confidence: float
    latency_ms: float
    cost_usd: float
    provider: str


class STTProvider(ABC):
    """Interfaz base para proveedores de Speech-to-Text.

    Cada implementación concreta debe reportar latencia y costo (RQ-01, RQ-03, RQ-04).
    El orchestrator itera sobre proveedores si el primario falla (RQ-06).
    """

    @abstractmethod
    async def transcribe(self, audio: bytes, language: str) -> STTResult: ...
