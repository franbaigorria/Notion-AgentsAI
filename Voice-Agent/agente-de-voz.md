# Agente de Voz

## One-Line Pitch

Agente de voz con acento argentino, capaz de responder de forma fluida sobre datos de negocio usando RAG, pensado para soporte, seguimiento y tareas comerciales simples.

## Problem

- Muchas interacciones repetitivas de soporte y seguimiento consumen tiempo humano y no escalan bien.
- Los asistentes de voz suelen sonar artificiales, perder contexto o alucinar cuando no tienen información suficiente.
- Para casos comerciales o de atención, la confianza cae fuerte cuando el agente suena ajeno al usuario o responde con poca naturalidad.

## User And Buyer

- Primary user: equipos de soporte, operaciones, ventas o customer success.
- Economic buyer: pyme o empresa que quiera automatizar interacciones sin contratar más personal para tareas repetitivas.
- Initial market or niche: empresas de servicios o comercios con alto volumen de consultas simples y seguimiento de clientes.

## MVP

- Un solo caso de uso inicial, no varios a la vez.
- Canal de voz con respuestas fluidas basadas en una base de conocimiento vía RAG.
- Acento argentino o, como mínimo, una voz que resulte natural para usuarios locales.
- Respuestas seguras ante incertidumbre: buscar, responder con cautela o escalar a humano.

### Explicitly Out Of Scope

- Cierre de ventas complejas.
- Reemplazo total de equipos humanos.
- Memoria avanzada multi-canal desde el día uno.
- Agente generalista para cualquier industria.

## AI Layer

- Core capabilities: voz, RAG, guardrails anti-alucinación y memoria acotada.
- Context model:
  - memoria de sesión para no perder el hilo de la conversación
  - memoria por cliente para continuidad entre interacciones, si el caso lo justifica
- Key quality constraints:
  - baja latencia
  - tono natural
  - alta precisión sobre datos reales
  - comportamiento seguro cuando no sabe

## Product Notes

- El diferencial inicial puede estar más en la experiencia local y la confiabilidad que en la complejidad técnica extrema.
- La percepción de “naturalidad” en voz probablemente sea tan importante como la precisión factual.
- Si el agente interrumpe mal, tarda demasiado o contesta con seguridad errónea, el producto pierde valor rápido.

## Use Cases

### Near-Term

- Soporte de preguntas frecuentes.
- Seguimiento simple a clientes.
- Confirmaciones, recordatorios o estados de trámite.

### Longer-Term

- Venta conversacional asistida.
- Calificación de leads.
- Seguimiento comercial más persuasivo y personalizado.
- Agente con lenguaje y tono muy cercano al de la población objetivo.

## Risks

### Technical

- Hallucinations when retrieved data is weak, stale, or missing.
- Latency too high for natural voice interaction.
- Voice quality or accent quality may be good enough in demos but weak in real calls.
- Poor memory design could create confusion between clients or sessions.
- Cost per conversation may get expensive before conversion value is proven.

### Business

- The first niche may not value voice enough to pay.
- Users may prefer WhatsApp or text over phone-style interactions.
- Trust barrier: customers may reject obviously artificial agents.
- Large incumbents could ship similar capabilities fast unless the wedge is strong.

## Moat Hypotheses

- Better domain data and retrieval quality.
- Better local conversational experience for Argentina or LatAm.
- Better workflow integration with the client's own business systems.
- Better operational metrics: resolution, conversion, retention, and lower cost per interaction.

## Suggested Repo

- Repo name: `agente-de-voz`
- Likely scope:
  - voice interface
  - retrieval layer
  - session memory
  - evaluation harness
  - business integration adapters

## Open Questions

- Which single use case should be the first wedge: soporte, seguimiento o ventas?
- Is voice really the best channel for the first market, or should the same engine start on chat or WhatsApp?
- How important is truly Argentine speech versus simply sounding natural and trustworthy?
- What level of memory is actually needed for version one?
- What metric matters most in the MVP: resolution rate, conversion, average handling time, or user satisfaction?
- When should the agent escalate to a human?

## Next Step

- Pick one narrow initial vertical and one narrow workflow.
- Define a success metric for the MVP.
- Test with a small set of real conversations and a constrained knowledge base.
- Validate whether the value is stronger in support, follow-up, or sales before broadening scope.

---

## Unsloth - Evaluación Técnica (2026-03-20)

### Qué es

Unsloth es una librería open-source para fine-tuning e inference local de modelos de lenguaje. Entrena modelos ~2x más rápido con ~70% menos VRAM, sin pérdida de precisión. Soporta TTS, visión, embeddings, RL, y 500+ modelos (Llama, Qwen, Mistral, Gemma, Phi, etc.). Tiene una UI propia (Unsloth Studio) y exporta a GGUF.

### Relevancia para esta idea

| Capa del agente | Cómo encaja Unsloth |
|---|---|
| Voz (TTS) | Fine-tuning de modelos TTS para lograr acento argentino específico |
| Lenguaje | Fine-tuning de LLM pequeño para tono, vocabulario y comportamiento del dominio (soporte/ventas) |
| RAG | Unsloth afirma que fine-tuning puede replicar las capacidades de RAG para conocimiento estático |
| Costo | Inference local reduce costo por conversación vs depender de APIs externas |
| Latencia | Modelos locales eliminan roundtrips a APIs, clave para voz en tiempo real |

### Stack sugerido con Unsloth

1. **MVP (validación)**: APIs externas (OpenAI/Anthropic para LLM + ElevenLabs para TTS) → rápido de lanzar, bajo riesgo
2. **Fase 2 (diferenciación)**: Unsloth fine-tune de un modelo pequeño (Qwen3-8B o similar) para el dominio específico
3. **Fase 3 (escala)**: Unsloth fine-tune de modelo TTS para acento argentino + inference local para reducir costos

### Consideraciones

**Pros:**
- Control total sobre el modelo, sin vendor lock-in
- El moat real del producto estaría en el fine-tuning (tono, acento, conocimiento de dominio)
- Costo operativo más bajo a escala vs APIs por conversación
- Soporte nativo para TTS fine-tuning = directamente aplicable al acento argentino
- Colabora oficialmente con los equipos de Qwen, Llama, Mistral, Gemma
- Open-source, sin licencias comerciales restrictivas

**Contras:**
- Requiere infraestructura GPU propia o deployment en cloud (costo fijo inicial)
- Para el MVP, es over-engineering: un agente con APIs valida más rápido
- Fine-tuning de TTS para un acento específico puede requerir datasets de audio curados
- Mantener modelos propios agrega complejidad operativa vs usar APIs

### Recomendación

No usar Unsloth para el MVP. Validar primero con APIs que el mercado quiere un agente de voz. Una vez validado, Unsloth es la herramienta ideal para construir el diferenciador técnico (acento, tono, conocimiento) y reducir costos a escala. Es el camino correcto para convertir "agente genérico con API" en "producto con moat defensible".
