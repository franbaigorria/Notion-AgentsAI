import time

from openai import AsyncOpenAI

from .base import LLMProvider, LLMResult

# GPT-4o pricing (USD por 1k tokens)
INPUT_COST_PER_1K = 0.0025
OUTPUT_COST_PER_1K = 0.0100


class OpenAILLM(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def complete(self, messages: list[dict], system: str) -> LLMResult:
        start = time.perf_counter()
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}] + messages,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        usage = response.usage
        cost = (usage.prompt_tokens / 1000 * INPUT_COST_PER_1K) + (
            usage.completion_tokens / 1000 * OUTPUT_COST_PER_1K
        )

        return LLMResult(
            content=response.choices[0].message.content,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            latency_ms=latency_ms,
            cost_usd=cost,
        )
