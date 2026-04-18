"""Implementación de LLMProvider usando Google Gemini.

Usa livekit-plugins-google (plugin nativo) para la integración con LiveKit AgentSession.
Para llamadas directas sin LiveKit usa el SDK google-genai.

Uso en AgentSession (LiveKit Agents 1.x):
    llm = GeminiLLM(model="gemini-3.1-flash-lite")
    session = AgentSession(llm=llm.as_livekit_plugin(), ...)

Uso directo (sin LiveKit, para RAG loop o tests):
    llm = GeminiLLM()
    result = await llm.complete(context)

Variable requerida: GEMINI_API_KEY
"""

import os
import time

from livekit.plugins import google as lk_google

from .base import LLMContext, LLMProvider, LLMResult

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
    def __init__(
        self, model: str = "gemini-3.1-flash-lite", api_key: str | None = None
    ):
        self.model = model
        # Precedence: explicit api_key → GOOGLE_API_KEY → GEMINI_API_KEY.
        # Unified vault key is "google" (see _PROVIDER_VAULT_KEYS); both env vars
        # tolerated for local dev backward compat.
        self.api_key = (
            api_key
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )
        if not self.api_key:
            raise ValueError(
                "Gemini API key not configured. Set GOOGLE_API_KEY (preferred) "
                "or GEMINI_API_KEY, or pass api_key explicitly."
            )

    def as_livekit_plugin(self) -> lk_google.LLM:
        """Retorna el plugin nativo de LiveKit para Google Gemini."""
        return lk_google.LLM(
            model=self.model,
            api_key=self.api_key,
            max_output_tokens=150,  # Importante para voz — respuestas cortas
        )

    async def complete(self, context: LLMContext) -> LLMResult:
        """Genera una respuesta usando el SDK google-genai directamente."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)

        contents = [
            types.Content(role=m.role, parts=[types.Part(text=m.content)])
            for m in context.messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=context.system or None,
            max_output_tokens=256,
        )

        start = time.monotonic()
        response = await client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )
        latency_ms = (time.monotonic() - start) * 1000

        input_tokens = response.usage_metadata.prompt_token_count or 0
        output_tokens = response.usage_metadata.candidates_token_count or 0
        cost_usd = (
            input_tokens * _INPUT_COST_PER_M / 1_000_000
            + output_tokens * _OUTPUT_COST_PER_M / 1_000_000
        )

        return LLMResult(
            content=response.text,
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
