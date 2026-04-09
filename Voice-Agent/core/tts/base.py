from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass
class TTSResult:
    latency_ms: float
    cost_usd: float
    provider: str


class TTSProvider(ABC):
    """Interfaz base para proveedores de Text-to-Speech.

    Devuelve un stream de audio — no espera a que esté completo (RQ-01).
    Reporta latencia y costo por síntesis (RQ-03, RQ-04).
    """

    @abstractmethod
    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[bytes]: ...
