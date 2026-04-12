"""Implementación de LLMProvider usando Groq Cloud.

Provee un LLM ultra rápido (TTFT ~150-200ms) compatible con OpenAI.
"""

import os
import time

from livekit.plugins import openai as lk_openai

from .base import LLMContext, LLMProvider, LLMResult

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


class GroqLLM(LLMProvider):
    def __init__(self, model: str = "llama-3.1-8b-instant"):
        self.model = model
        self.api_key = os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY no está configurada")

    def as_livekit_plugin(self) -> lk_openai.LLM:
        """Retorna el plugin LiveKit configurado para apuntar a Groq."""
        return lk_openai.LLM(
            model=self.model,
            base_url="https://api.groq.com/openai/v1",
            api_key=self.api_key,
            max_completion_tokens=200,  # maximo 2 oraciones por turno segun persona
        )

    async def complete(self, context: LLMContext) -> LLMResult:
        """Genera una respuesta usando la API de Groq directamente."""
        import openai

        client = openai.AsyncOpenAI(
            base_url="https://api.groq.com/openai/v1", api_key=self.api_key
        )
        messages = []
        if context.system:
            messages.append({"role": "system", "content": context.system})
        messages += [{"role": m.role, "content": m.content} for m in context.messages]

        start = time.monotonic()
        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=256,
            messages=messages,
        )
        latency_ms = (time.monotonic() - start) * 1000

        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        return LLMResult(
            content=response.choices[0].message.content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=0.0,  # Free/Cheap tier depends on size
            provider="groq",
        )

    async def optimize_for_tts(self, text: str) -> LLMResult:
        from .base import Message

        context = LLMContext(
            system=_TTS_OPTIMIZER_SYSTEM,
            messages=[Message(role="user", content=text)],
        )
        return await self.complete(context)
