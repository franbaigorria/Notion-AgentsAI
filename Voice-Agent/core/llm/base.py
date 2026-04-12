from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class LLMResult:
    content: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float
    provider: str


@dataclass
class LLMContext:
    messages: list[Message] = field(default_factory=list)
    system: str = ""


class LLMProvider(ABC):
    """Interfaz base para proveedores de LLM.

    Implementa el patrón doble-agente:
    - complete(): genera la respuesta correcta
    - optimize_for_tts(): adapta la respuesta para síntesis de voz
      (sin markdown, frases cortas, conectores del habla argentina)

    Reporta tokens y costo por llamada (RQ-03, RQ-04).
    """

    @abstractmethod
    async def complete(self, context: LLMContext) -> LLMResult: ...

    async def stream(self, context: LLMContext) -> "AsyncIterator[str]":
        """Stream de tokens de respuesta. Default: no implementado.

        No es @abstractmethod para no romper implementaciones existentes.
        Usado en direct-mode. En el pipeline LiveKit el streaming lo maneja
        AgentSession + livekit.plugins.anthropic nativamente.
        """
        raise NotImplementedError(
            f"{type(self).__name__} no implementa stream(). "
            "Usar complete() o implementar stream() en la subclase."
        )
        # Necesario para que Python infiera el tipo AsyncIterator[str]
        yield  # type: ignore[misc]

    @abstractmethod
    async def optimize_for_tts(self, text: str) -> LLMResult:
        """Convierte una respuesta al estilo natural hablado en español rioplatense.

        Sin markdown, sin bullets, frases < 20 palabras, conectores orales.
        """
        ...
