"""Implementación de LLMProvider usando OpenAI.

Uso en AgentSession (LiveKit Agents 1.x):
    llm = OpenAILLM(model="gpt-4o-mini")
    session = AgentSession(llm=llm.as_livekit_plugin(), ...)

Uso directo (sin LiveKit, para RAG loop o tests):
    llm = OpenAILLM()
    result = await llm.complete(context)
    optimized = await llm.optimize_for_tts(result.content)
"""

import time

from livekit.plugins import openai as lk_openai

from .base import LLMContext, LLMProvider, LLMResult

# Precios gpt-4o-mini (USD por millón de tokens)
_INPUT_COST_PER_M = 0.15
_OUTPUT_COST_PER_M = 0.60

_TTS_OPTIMIZER_SYSTEM = """\
Sos un optimizador de respuestas para síntesis de voz en español rioplatense.

Recibís una respuesta y la convertís para que suene natural cuando la lee un TTS.

Reglas:
- Sin markdown, sin bullets, sin asteriscos, sin numeración
- Frases cortas, máximo 20 palabras cada una
- Usá conectores del habla argentina: "Mirá,", "Y sabés qué,", "Dale,", "Claro que sí."
- Si hay listas, convertirlas en frases seguidas separadas por punto
- No agregues información nueva, solo reformateás
- Devolvé únicamente el texto optimizado, sin explicaciones
"""


class OpenAILLM(LLMProvider):
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None):
        self.model = model
        self.api_key = api_key

    def as_livekit_plugin(self) -> lk_openai.LLM:
        """Retorna el plugin LiveKit para usar en AgentSession."""
        kwargs: dict = {"model": self.model}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        return lk_openai.LLM(**kwargs)

    async def complete(self, context: LLMContext) -> LLMResult:
        """Genera una respuesta usando la API de OpenAI directamente."""
        import openai

        client = openai.AsyncOpenAI()
        messages = []
        if context.system:
            messages.append({"role": "system", "content": context.system})
        messages += [{"role": m.role, "content": m.content} for m in context.messages]

        start = time.monotonic()
        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            messages=messages,
        )
        latency_ms = (time.monotonic() - start) * 1000

        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        cost_usd = (
            input_tokens * _INPUT_COST_PER_M / 1_000_000
            + output_tokens * _OUTPUT_COST_PER_M / 1_000_000
        )

        return LLMResult(
            content=response.choices[0].message.content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            provider="openai",
        )

    async def optimize_for_tts(self, text: str) -> LLMResult:
        """Adapta texto para síntesis de voz. Implementa Agent 2 del patrón doble-agente."""
        from .base import Message

        context = LLMContext(
            system=_TTS_OPTIMIZER_SYSTEM,
            messages=[Message(role="user", content=text)],
        )
        return await self.complete(context)
