from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


@dataclass
class KnowledgeResult:
    context: str
    score: float
    source: Literal["kb_local", "web", "none"]
    latency_ms: float


class KnowledgeProvider(ABC):
    """Interfaz base para Recuperación de Conocimiento Documental (Knowledge Access).

    Reemplaza al antiguo RAGProvider.
    Se usa para recuperar información estática o semi-estructurada (FAQs, políticas, coberturas).
    La búsqueda siempre se filtra por vertical para no mezclar KBs entre negocios (RQ-02/RQ-03).
    """

    @abstractmethod
    async def retrieve(self, query: str, vertical: str) -> KnowledgeResult: ...
