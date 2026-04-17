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

    Recupera información estática o semi-estructurada (FAQs, políticas, coberturas).
    La búsqueda se filtra por tenant_id para garantizar aislamiento total entre clientes.

    Convención de naming en Qdrant: colección = kb_{tenant_id}
    Ejemplo: tenant "clinica_del_valle" → colección "kb_clinica_del_valle"
    """

    @abstractmethod
    async def retrieve(self, query: str, tenant_id: str) -> KnowledgeResult: ...
