"""Implementación de LLMProvider usando Google Gemini.

Usa el endpoint OpenAI-compatible de Google AI Studio:
  https://generativelanguage.googleapis.com/v1beta/openai/

No requiere dependencias adicionales — usa livekit-plugins-openai con base_url custom,
igual que GroqLLM.

Uso en AgentSession (LiveKit Agents 1.x):
    llm = GeminiLLM(model="gemini-3.1-flash-lite")
    session = AgentSession(llm=llm.as_livekit_plugin(), ...)

Uso directo (sin LiveKit, para RAG loop o tests):
    llm = GeminiLLM()
    result = await llm.complete(context)
"""

import os
import time

from livekit.plugins import openai as lk_openai

from .base import LLMContext, LLMProvider, LLMResult

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Precios Gemini Flash Lite (USD por millón de tokens) — actualizar según pricing de Google AI
_INPUT_COST_PER_M = 0.075
_OUTPUT_COST_PER_M = 0.30

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


class GeminiLLM(LLMProvider):
    def __init__(self, model: str = "gemini-3.1-flash-lite"):
        self.model = model
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY no está configurada")

    def as_livekit_plugin(self) -> lk_openai.LLM:
        """Retorna el plugin LiveKit configurado para apuntar a Google Gemini."""
        return lk_openai.LLM(
            model=self.model,
            base_url=_GEMINI_BASE_URL,
            api_key=self.api_key,
            max_completion_tokens=150,  # Importante para voz — respuestas cortas
        )

    async def complete(self, context: LLMContext) -> LLMResult:
        """Genera una respuesta usando el endpoint OpenAI-compatible de Google."""
        import openai

        client = openai.AsyncOpenAI(
            base_url=_GEMINI_BASE_URL,
            api_key=self.api_key,
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
            provider="gemini",
        )

    async def optimize_for_tts(self, text: str) -> LLMResult:
        from .base import Message

        context = LLMContext(
            system=_TTS_OPTIMIZER_SYSTEM,
            messages=[Message(role="user", content=text)],
        )
        return await self.complete(context)
