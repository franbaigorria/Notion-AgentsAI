from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Memory:
    key: str
    value: str


class MemoryProvider(ABC):
    """Interfaz base para memoria persistente entre llamadas.

    Identificación por número de teléfono. La memoria es por usuario y por vertical,
    no se mezcla entre negocios (RQ-02).
    """

    @abstractmethod
    async def get(self, user_id: str, vertical: str) -> list[Memory]: ...

    @abstractmethod
    async def save(self, user_id: str, vertical: str, transcript: str) -> None: ...
