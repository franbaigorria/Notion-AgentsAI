# tests/

Suite de tests del sistema. Cubre el pipeline de voz, los adapters, y los flows de conversación.

**Por qué existe:** El modo de prueba local (RQ-05) hace posible testear el pipeline completo sin Twilio. Esta carpeta organiza esos tests de forma que sean repetibles, ejecutables en CI, y útiles para comparar proveedores.

**Estado:** Se arma en Fase 1 cuando empieza el código. La estructura se define ahora para que el diseño lo tenga en cuenta desde el principio (Strict TDD Mode configurado).

## Estructura planificada

```
tests/
  unit/
    core/          # tests de cada capa aislada (STT, TTS, LLM, RAG)
    adapters/      # tests de cada adapter con mocks de APIs externas
  integration/
    pipeline/      # tests del pipeline completo con LocalInput (RQ-05)
    flows/         # tests de conversaciones end-to-end por vertical
  fixtures/
    audio/         # archivos .wav de audio de prueba
    transcripts/   # conversaciones de prueba en formato texto
```

## Requerimientos

- **RQ-05** — los tests de integración usan `LocalInput` como telephony provider; no necesitan Twilio
- **RQ-01** — los tests unitarios verifican que cambiar de provider no cambia el comportamiento del core
