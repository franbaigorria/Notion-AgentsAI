from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class CapabilityResult:
    success: bool
    data: dict[str, Any]
    error_message: str | None = None


class CapabilityProvider(ABC):
    """Interfaz base para Acceso a Datos Operativos (Operational Access).

    A diferencia de Knowledge (documentos) o Memory (historial),
    Capabilities define acciones transaccionales sobre sistemas vivos.
    Ej: 'scheduling' (turnos), 'insurance_check' (cobertura), 'crm_update'.

    Cada VerticalBundle declara qué capabilities necesita en `integrations.yaml`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre único de la capability (ej: 'scheduling')."""
        ...

    @abstractmethod
    async def execute(self, action: str, params: dict[str, Any], vertical: str) -> CapabilityResult:
        """Ejecuta una acción transaccional.

        Args:
            action: Nombre de la acción (ej: 'book_appointment').
            params: Parámetros tipados extraídos por el LLM.
            vertical: Contexto del vertical para routear al tenant correcto.
        """
        ...
