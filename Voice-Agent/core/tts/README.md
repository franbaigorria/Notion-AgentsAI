# core/tts/

Capa de Text-to-Speech. Convierte texto en audio y lo entrega como stream.

**Por qué existe:** La calidad de voz en español rioplatense varía enormemente entre proveedores. ElevenLabs es el primario por naturalidad, pero necesita fallback ante downtime. El streaming es crítico — el usuario empieza a escuchar mientras el audio se termina de generar, lo que determina la latencia percibida.

## Contrato de la interfaz

```python
class TTSProvider:
    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[bytes]
    # Stream de audio — no espera a que esté completo
```

## Implementaciones planificadas

| Archivo | Proveedor | Estado |
|---------|-----------|--------|
| `elevenlabs.py` | ElevenLabs (eleven_turbo_v2_5) | primario |
| `openai_tts.py` | OpenAI TTS | fallback |

## Requerimientos

- **RQ-01** — interfaz única, implementaciones intercambiables
- **RQ-03** — cada implementación reporta `latency_ms` y `provider`
- **RQ-04** — cada implementación reporta `cost_usd` (basado en caracteres)
- **RQ-06** — fallback automático si ElevenLabs falla
