from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


@dataclass
class RAGResult:
    context: str
    score: float
    source: Literal["kb_local", "web", "none"]
    latency_ms: float


class RAGProvider(ABC):
    """Interfaz base para Retrieval-Augmented Generation.

    Busca primero en KB local, cae a web si el score es bajo, escala si no hay resultado.
    La búsqueda se filtra por vertical para no mezclar KBs entre negocios (RQ-02).
    """

    @abstractmethod
    async def retrieve(self, query: str, vertical: str) -> RAGResult: ...
