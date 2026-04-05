# core/telephony/

Capa de entrada y salida de audio. Recibe la llamada y entrega el audio de respuesta.

**Por qué existe:** Es la única capa que sabe si el agente está corriendo en producción (Twilio) o en modo de prueba local. El resto del pipeline no sabe la diferencia — recibe bytes de audio y devuelve bytes de audio. Esta separación es lo que hace posible el modo de prueba sin telefonía real.

## Contrato de la interfaz

```python
class TelephonyProvider:
    async def receive_audio(self) -> AsyncIterator[bytes]   # stream de audio entrante
    async def send_audio(self, audio: AsyncIterator[bytes]) # stream de audio saliente
    def get_caller_id(self) -> str                          # número de teléfono del llamante
```

## Implementaciones

| Archivo | Descripción | Cuándo se usa |
|---------|-------------|---------------|
| `twilio.py` | WebSocket con Twilio Media Streams | producción |
| `local_input.py` | Lee texto o archivo de audio del disco | desarrollo y tests |

## Modo de prueba (`local_input.py`)

```bash
python -m voice_agent.agent --input-mode=text   # escribe texto en terminal
python -m voice_agent.agent --input-mode=file --audio=test.wav
```

El resto del pipeline (STT, RAG, LLM, TTS) corre idéntico al de producción.

## Requerimientos

- **RQ-05** — `LocalInput` permite correr el pipeline completo sin Twilio
- **RQ-01** — `TelephonyProvider` es una interfaz; Twilio es una implementación más
