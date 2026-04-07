from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResult:
    content: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict], system: str) -> LLMResult: ...
