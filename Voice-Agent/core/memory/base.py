from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Memory:
    key: str
    value: str


class MemoryProvider(ABC):
    """Interfaz base para memoria persistente entre llamadas.

    Identificación por número de teléfono (user_id) + tenant_id.
    Un mismo usuario que llama a dos clientes distintos del mismo vertical
    tiene memoria completamente separada.

    Convención de namespace en Mem0/Qdrant: mem_{tenant_id}
    Ejemplo: tenant "clinica_del_valle" → namespace "mem_clinica_del_valle"
    """

    @abstractmethod
    async def get(self, user_id: str, tenant_id: str) -> list[Memory]: ...

    @abstractmethod
    async def save(self, user_id: str, tenant_id: str, transcript: str) -> None: ...
