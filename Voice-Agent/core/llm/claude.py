"""Implementación de LLMProvider usando Anthropic Claude.

Proveedor primario. Implementa el patrón doble-agente:
- Agent 1: genera la respuesta correcta con toda la información
- Agent 2 (TTS optimizer): convierte la respuesta a texto natural hablado
  (sin markdown, frases < 20 palabras, conectores del habla argentina)

Uso en AgentSession (LiveKit Agents 1.x):
    llm = ClaudeLLM(model="claude-sonnet-4-6")
    session = AgentSession(llm=llm.as_livekit_plugin(), ...)

Uso directo (sin LiveKit, para RAG loop o tests):
    llm = ClaudeLLM()
    result = await llm.complete(context)
    optimized = await llm.optimize_for_tts(result.content)
"""

import time

from livekit.plugins import anthropic as lk_anthropic

from .base import LLMContext, LLMProvider, LLMResult

# Precios Claude Sonnet 4.6 (USD por millón de tokens)
_INPUT_COST_PER_M = 3.0
_OUTPUT_COST_PER_M = 15.0

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


class ClaudeLLM(LLMProvider):
    def __init__(
        self, model: str = "claude-sonnet-4-6", api_key: str | None = None
    ):
        self.model = model
        self.api_key = api_key

    def as_livekit_plugin(self) -> lk_anthropic.LLM:
        """Retorna el plugin LiveKit para usar en AgentSession."""
        kwargs: dict = {"model": self.model}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        return lk_anthropic.LLM(**kwargs)

    async def complete(self, context: LLMContext) -> LLMResult:
        """Genera una respuesta usando la API de Anthropic directamente."""
        import anthropic

        client = anthropic.AsyncAnthropic()
        messages = [{"role": m.role, "content": m.content} for m in context.messages]

        start = time.monotonic()
        response = await client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=context.system,
            messages=messages,
        )
        latency_ms = (time.monotonic() - start) * 1000

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost_usd = (
            input_tokens * _INPUT_COST_PER_M / 1_000_000
            + output_tokens * _OUTPUT_COST_PER_M / 1_000_000
        )

        return LLMResult(
            content=response.content[0].text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            provider="claude",
        )

    async def optimize_for_tts(self, text: str) -> LLMResult:
        """Adapta texto para síntesis de voz. Implementa Agent 2 del patrón doble-agente."""
        from .base import Message

        context = LLMContext(
            system=_TTS_OPTIMIZER_SYSTEM,
            messages=[Message(role="user", content=text)],
        )
        return await self.complete(context)
