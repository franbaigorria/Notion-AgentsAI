# core/llm/

Capa de Language Model. Genera respuestas a partir del contexto de la conversación y el resultado del RAG.

**Por qué existe:** El LLM es el componente más sensible a cambios de proveedor en términos de costo y calidad. Claude y GPT-4o tienen diferencias de latencia y precio que conviene poder evaluar en producción. Esta capa implementa además el patrón de doble-agente: el primero genera la respuesta correcta, el segundo la optimiza para que suene natural hablada.

## Contrato de la interfaz

```python
class LLMProvider:
    async def complete(self, messages: list[Message], system: str) -> LLMResult
    # LLMResult: content, input_tokens, output_tokens, latency_ms, cost_usd
```

## Implementaciones planificadas

| Archivo | Proveedor | Estado |
|---------|-----------|--------|
| `claude.py` | Anthropic Claude Sonnet 4.6 | primario |
| `openai.py` | OpenAI GPT-4o | fallback |

## Patrón doble-agente

```
Agente 1 (respuesta): genera la respuesta correcta con toda la información
Agente 2 (TTS optimizer): convierte la respuesta a texto natural hablado
  — sin markdown, sin bullets, frases < 20 palabras, conectores del habla argentina
```

## Requerimientos

- **RQ-01** — interfaz única, implementaciones intercambiables
- **RQ-03** — reporta `latency_ms`, `provider`, `tokens_used`
- **RQ-04** — reporta `cost_usd` (input + output tokens × rate)
- **RQ-06** — fallback automático entre proveedores
