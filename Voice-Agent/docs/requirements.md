# Requerimientos de Arquitectura — Voice Agent Platform

Estos son los requerimientos que guían las decisiones de arquitectura del proyecto.
Toda decisión técnica debe justificarse contra al menos uno de estos requerimientos.

---

## RQ-01 — Intercambio de proveedor por capa

**Qué:** Cada capa del pipeline de voz (STT, LLM, TTS, telefonía) debe poder reemplazarse por otro proveedor sin modificar el resto del sistema.

**Por qué importa:** Los proveedores de IA evolucionan rápido. Lo que hoy tiene mejor latencia o calidad puede cambiar en meses. Quedar atado a un proveedor es un riesgo operativo y de costo.

**Cómo lo medimos:** Cambiar de Whisper a Deepgram (o de Claude a GPT-4o) requiere modificar máximo un archivo de configuración o una clase concreta. El core no cambia.

**Implementación:** Adapter pattern — cada capa expone una interfaz base (`STTProvider`, `LLMProvider`, `TTSProvider`). Las implementaciones concretas son intercambiables.

---

## RQ-02 — Vertical intercambiable (negocio configurable)

**Qué:** El mismo core del agente debe poder atender distintos rubros de negocio (clínicas, inmobiliarias, etc.) mediante configuración, sin tocar código.

**Por qué importa:** El producto es una plataforma, no un agente específico de clínicas. La capacidad de lanzar un nuevo vertical en días (no semanas) es el diferenciador del negocio.

**Cómo lo medimos:** Cambiar de vertical implica solo apuntar a un directorio de configuración diferente. El core arranca sin saber de qué negocio se trata hasta que lee la config.

**Implementación:** Cada vertical vive en `verticals/{nombre}/` con 6 archivos de configuración: `config.yaml`, `persona.md`, `flows.yaml`, `kb_sources.yaml`, `integrations.yaml`, `escalation_rules.yaml`.

---

## RQ-03 — Observabilidad por paso

**Qué:** Cada capa del pipeline registra su latencia, proveedor usado, y resultado clave. Los datos están disponibles para análisis post-llamada.

**Por qué importa:** Sin observabilidad no hay aprendizaje. No se pueden comparar proveedores, detectar cuellos de botella, ni construir el dashboard de métricas para el cliente.

**Cómo lo medimos:** Al final de cada llamada existe un registro con al menos estos campos por capa:

```
stt_latency_ms    stt_provider    transcript_length_chars
rag_latency_ms    rag_score       rag_source (kb_local | web | none)
llm_latency_ms    llm_provider    tokens_used
tts_latency_ms    tts_provider    audio_duration_ms
total_latency_ms  resolution_type (resolved | escalated | abandoned)
```

**Implementación:** Cada adapter registra sus métricas en un objeto de tracing que se persiste al cierre de la llamada.

---

## RQ-04 — Costo por conversación trazable

**Qué:** El sistema calcula el costo real de cada llamada, desglosado por proveedor, y lo persiste junto al log de la conversación.

**Por qué importa:** El modelo de negocio es por minuto. Para saber el margen real hay que conocer el costo exacto por llamada. También informa cuándo conviene cambiar de proveedor por costo.

**Cómo lo medimos:** Al cierre de cada llamada existe un registro con:

```
costo_stt_usd     costo_llm_usd     costo_tts_usd
costo_telefonia_usd                 costo_total_usd
duracion_min      costo_por_min_usd
```

**Implementación:** Cada adapter reporta su costo (basado en tokens, caracteres o segundos según la API). El orquestador suma y persiste.

---

## RQ-05 — Modo de prueba sin telefonía real

**Qué:** El pipeline completo puede ejecutarse inyectando texto o audio grabado, sin necesitar Twilio ni una llamada real.

**Por qué importa:** Desarrollar y testear con llamadas reales es lento, costoso y no repetible. La iteración rápida requiere poder correr el agente localmente con inputs controlados.

**Cómo lo medimos:** Existe un modo `--input-mode=text|file` que bypasea la capa de telefonía. El resto del pipeline (STT, RAG, LLM, TTS) corre idéntico al de producción.

**Implementación:** La capa de telefonía (`TelephonyProvider`) tiene una implementación `LocalInput` que acepta texto o archivo de audio como fuente. El core no sabe la diferencia.

---

## RQ-06 — Degradación graceful por proveedor

**Qué:** Si un proveedor falla (timeout, error de API, downtime), el sistema cae automáticamente al proveedor de fallback configurado. La llamada no muere.

**Por qué importa:** En producción con llamadas reales, una caída de ElevenLabs no puede cortar la comunicación con un paciente. La resiliencia es parte de la experiencia del producto.

**Cómo lo medimos:** Si el proveedor primario falla, el sistema usa el fallback en menos de 500ms adicionales y registra el evento. El usuario no percibe la diferencia (excepto posible variación de voz).

**Implementación:** Cada adapter acepta una lista de proveedores ordenados por preferencia. El orquestador itera hasta el primero que responde. El fallback se configura por vertical si es necesario.

```yaml
# Ejemplo en config.yaml del vertical
tts:
  primary: elevenlabs
  fallback: openai_tts
stt:
  primary: whisper
  fallback: deepgram
```

---

## Relación con el PLAN.md

| Requerimiento | Fase del PLAN donde impacta |
|---|---|
| RQ-01 Intercambio de proveedor | Fase 0 — estructura base del repo |
| RQ-02 Vertical intercambiable | Fase 6 — Vertical Adapter |
| RQ-03 Observabilidad | Fase 1 — loop de voz, Fase 7 — dashboard |
| RQ-04 Costo trazable | Fase 7 — facturación |
| RQ-05 Modo de prueba | Fase 0 y todo el desarrollo |
| RQ-06 Degradación graceful | Fase 1 en adelante |

Los requerimientos RQ-01, RQ-02 y RQ-05 deben estar resueltos desde la Fase 0.
Los demás pueden implementarse gradualmente pero su diseño debe estar pensado desde el día uno.
