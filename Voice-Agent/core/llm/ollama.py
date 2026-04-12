"""Implementación de LLMProvider usando Ollama (modelos locales).

Proveedor para inferencia local — elimina latencia de red (~400-500ms
desde Argentina). Ideal para conversaciones transaccionales.

Usa la API compatible con OpenAI de Ollama (puerto 11434).

Uso en AgentSession (LiveKit Agents 1.x):
    llm = OllamaLLM(model="gemma4:e4b")
    session = AgentSession(llm=llm.as_livekit_plugin(), ...)

Uso directo (sin LiveKit, para RAG loop o tests):
    llm = OllamaLLM()
    result = await llm.complete(context)
"""

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

_DEFAULT_BASE_URL = "http://localhost:11434/v1"


class OllamaLLM(LLMProvider):
    def __init__(
        self,
        model: str = "gemma4:e4b",
        base_url: str = _DEFAULT_BASE_URL,
    ):
        self.model = model
        self.base_url = base_url

    def as_livekit_plugin(self) -> lk_openai.LLM:
        """Retorna el plugin LiveKit (OpenAI-compatible) apuntando a Ollama local.

        Usa LLM() directo en vez de with_ollama() para poder pasar
        max_completion_tokens — with_ollama() no expone ese parámetro.
        """
        return lk_openai.LLM(
            model=self.model,
            base_url=self.base_url,
            api_key="ollama",
            max_completion_tokens=150,  # Respuestas breves — evita picos de 5-12s TTFT
        )

    async def complete(self, context: LLMContext) -> LLMResult:
        """Genera una respuesta usando Ollama vía su API OpenAI-compatible."""
        import openai

        client = openai.AsyncOpenAI(
            base_url=self.base_url,
            api_key="ollama",  # Ollama no requiere API key
        )
        messages = []
        if context.system:
            messages.append({"role": "system", "content": context.system})
        messages += [{"role": m.role, "content": m.content} for m in context.messages]

        start = time.monotonic()
        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=150,  # Respuestas breves — voz conversacional, no redacción
            messages=messages,
        )
        latency_ms = (time.monotonic() - start) * 1000

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        return LLMResult(
            content=response.choices[0].message.content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=0.0,  # Local — sin costo por inferencia
            provider="ollama",
        )

    async def optimize_for_tts(self, text: str) -> LLMResult:
        """Adapta texto para síntesis de voz. Implementa Agent 2 del patrón doble-agente."""
        from .base import Message

        context = LLMContext(
            system=_TTS_OPTIMIZER_SYSTEM,
            messages=[Message(role="user", content=text)],
        )
        return await self.complete(context)
