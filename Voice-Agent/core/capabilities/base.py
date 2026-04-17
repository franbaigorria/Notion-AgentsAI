from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class CapabilityResult:
    success: bool
    data: dict[str, Any]
    error_message: str | None = None


class CapabilityProvider(ABC):
    """Interfaz base para Acceso Operativo (Operational Access) — Port/Adapter pattern.

    A diferencia de Knowledge (documentos) o Memory (historial),
    Capabilities define acciones transaccionales sobre sistemas externos vivos.
    Ejemplos: agendar turno, verificar cobertura, actualizar CRM.

    Cada tenant declara qué capabilities activa en su `integrations.yaml`.
    El orchestrator llama a `as_livekit_tool()` por cada capability para
    registrarlas como function_tools en el AgentSession.

    Convención de tenant_id: se pasa en execute() para que el adapter
    pueda routear al sistema correcto del cliente (ej: su Google Calendar).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre único de la capability — usado como nombre del tool en el LLM."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Descripción en lenguaje natural — el LLM la usa para decidir cuándo invocar el tool."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """JSON Schema de los parámetros que acepta el tool.

        Ejemplo:
            {
                "type": "object",
                "properties": {
                    "especialidad": {"type": "string"},
                    "fecha": {"type": "string", "format": "date"},
                },
                "required": ["especialidad"],
            }
        """
        ...

    @abstractmethod
    async def execute(self, action: str, params: dict[str, Any], tenant_id: str) -> CapabilityResult:
        """Ejecuta una acción transaccional en el sistema externo del tenant.

        Args:
            action: Nombre de la acción (ej: "book_appointment").
            params: Parámetros tipados extraídos por el LLM (validados contra `parameters`).
            tenant_id: ID del cliente — el adapter lo usa para conectar al sistema correcto.

        Returns:
            CapabilityResult con success=True y data, o success=False y error_message.
            NUNCA debe lanzar excepción — siempre retornar un CapabilityResult.
        """
        ...

    def as_livekit_tool(self) -> dict[str, Any]:
        """Retorna el descriptor del tool para registro en LiveKit AgentSession.

        Construye el descriptor a partir de las propiedades abstractas `name`,
        `description` y `parameters`. El orchestrator consume este dict para
        registrar el tool como function_tool del LLM.

        Returns:
            Dict con keys "name", "description", "parameters" (JSON Schema).
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
