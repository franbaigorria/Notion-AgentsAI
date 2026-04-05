# core/stt/

Capa de Speech-to-Text. Convierte el stream de audio del usuario en texto.

**Por qué existe:** El STT es una capa con múltiples proveedores viables (Whisper, Deepgram, ElevenLabs STT) con diferencias significativas en latencia, costo y precisión para español argentino. Aislarla detrás de una interfaz permite cambiar de proveedor con un cambio de configuración.

## Contrato de la interfaz

```python
class STTProvider:
    async def transcribe(self, audio: bytes, language: str) -> STTResult
    # STTResult: transcript, confidence, latency_ms, cost_usd
```

## Implementaciones planificadas

| Archivo | Proveedor | Estado |
|---------|-----------|--------|
| `whisper.py` | OpenAI Whisper | primario |
| `deepgram.py` | Deepgram Nova-2 | fallback |

## Requerimientos

- **RQ-01** — interfaz única, implementaciones intercambiables
- **RQ-03** — cada implementación reporta `latency_ms` y `provider`
- **RQ-04** — cada implementación reporta `cost_usd`
- **RQ-06** — el orchestrator itera proveedores si el primario falla
