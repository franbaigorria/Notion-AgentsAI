# core/orchestrator/

Coordina el pipeline completo de una llamada. Es el único componente que conoce todas las capas.

**Por qué existe:** Alguien tiene que coordinar el flujo STT → RAG → LLM → TTS, acumular las métricas de cada capa, calcular el costo total, y decidir qué proveedor usar (primario o fallback). Ese rol es del orchestrator. Nada más en el sistema tiene visión completa de la llamada.

## Responsabilidades

1. Cargar la configuración del vertical al inicio de la llamada
2. Recuperar la memoria del usuario (por número de teléfono)
3. Ejecutar el loop STT → RAG → LLM → TTS por cada turno
4. Acumular métricas y costos por capa
5. Detectar triggers de escalación
6. Guardar memoria y persistir el log al cierre

## Objeto de tracing (por llamada)

```python
CallTrace:
  call_id, vertical, phone, start_time, duration_ms
  turns: list[TurnTrace]
    stt: {provider, latency_ms, cost_usd, transcript}
    rag: {latency_ms, score, source}
    llm: {provider, latency_ms, cost_usd, tokens}
    tts: {provider, latency_ms, cost_usd}
  resolution: resolved | escalated | abandoned
  total_cost_usd
```

## Requerimientos

- **RQ-03** — produce el CallTrace completo con métricas por capa
- **RQ-04** — calcula `total_cost_usd` sumando costos de cada provider
- **RQ-05** — acepta un `TelephonyProvider` que puede ser Twilio o LocalInput
- **RQ-06** — implementa el retry con fallback por capa
