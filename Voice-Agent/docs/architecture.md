# Arquitectura Técnica — Voice Agent Platform

## Principio de diseño

El agente de voz es una **plataforma con un core invariante** y una **capa de configuración vertical**.
El core nunca cambia. El vertical se configura en YAML + texto.

Agregar un nuevo vertical no requiere tocar el core — solo crear archivos de configuración.

---

## Diagrama de flujo principal

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LLAMADA ENTRANTE                             │
│                         (Twilio webhook)                            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      CARGA DEL VERTICAL                             │
│  Lee config/ del vertical → persona, flows, kb_sources, reglas      │
│  Recupera memoria del paciente (Mem0 → Qdrant) por número entrante  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       LOOP DE CONVERSACIÓN                          │
│                                                                     │
│  Audio del usuario (stream)                                         │
│       ↓                                                             │
│  Whisper STT → texto                                                │
│       ↓                                                             │
│  Intent Detection → ¿qué quiere el usuario?                        │
│       ↓                                                             │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                  AUTONOMOUS RAG                            │    │
│  │  Búsqueda en KB local (Qdrant) con score de relevancia     │    │
│  │       ↓ si score < threshold                               │    │
│  │  Búsqueda web (DuckDuckGo/Tavily) como fallback            │    │
│  │       ↓ si sigue sin resultado                             │    │
│  │  Flag: necesita escalación                                 │    │
│  └────────────────────────────────────────────────────────────┘    │
│       ↓                                                             │
│  Agente 1: genera respuesta (LLM — Claude/GPT-4o)                  │
│       ↓                                                             │
│  Agente 2: optimiza para TTS (frases cortas, sin markdown)          │
│       ↓                                                             │
│  ElevenLabs TTS → stream de audio                                   │
│       ↓                                                             │
│  Twilio reproduce al llamante                                       │
│                                                                     │
│  [repite hasta: cuelgue / escalación / resolución]                 │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
   ┌─────────────────────┐         ┌─────────────────────────┐
   │   CIERRE NORMAL     │         │   ESCALACIÓN A HUMANO   │
   │                     │         │                         │
   │ Guarda en Mem0:     │         │ Resumen de conversación │
   │ - obra social       │         │ Notificación a staff    │
   │ - médico preferido  │         │ Transfer Twilio         │
   │ - último turno      │         │ Fallback: buzón + SMS   │
   │ - nombre si lo dio  │         └─────────────────────────┘
   └─────────────────────┘
```

---

## Estructura del repositorio

```
voice-agent/
├── core/                          # El motor — NO cambia por vertical
│   ├── stt/                       # Whisper STT pipeline
│   ├── tts/                       # ElevenLabs TTS pipeline
│   ├── llm/                       # LLM client (Claude / GPT-4o)
│   ├── rag/                       # Autonomous RAG (Qdrant + FastEmbed + web fallback)
│   ├── memory/                    # Mem0 + Qdrant memory layer
│   ├── orchestrator/              # OpenAI Agents SDK — orquesta los agentes
│   ├── escalation/                # Detector de escalación + handoff
│   └── telephony/                 # Twilio webhook handler + stream
│
├── verticals/                     # Configuración por vertical
│   ├── clinica/
│   │   ├── config.yaml            # nombre, voz ElevenLabs, idioma, timezone
│   │   ├── persona.md             # cómo habla, qué puede/no puede hacer
│   │   ├── flows.yaml             # agendar turno, consulta cobertura, info, reagendar
│   │   ├── kb_sources.yaml        # URLs a crawlear, PDFs a ingestar, APIs a conectar
│   │   ├── integrations.yaml      # Google Calendar, Docplanner, etc.
│   │   └── escalation_rules.yaml  # triggers de escalación + contacto del staff
│   │
│   ├── inmobiliaria/
│   │   ├── config.yaml
│   │   ├── persona.md
│   │   ├── flows.yaml             # consulta de propiedad, pre-calificación, visita
│   │   ├── kb_sources.yaml
│   │   ├── integrations.yaml
│   │   └── escalation_rules.yaml
│   │
│   └── template/                  # Plantilla vacía para un nuevo vertical
│       ├── config.yaml
│       ├── persona.md
│       ├── flows.yaml
│       ├── kb_sources.yaml
│       ├── integrations.yaml
│       └── escalation_rules.yaml
│
├── adapters/                      # Conectores a sistemas externos
│   ├── calendar/
│   │   ├── google_calendar.py
│   │   └── docplanner.py
│   ├── crm/
│   │   └── base.py                # Interface base para cualquier CRM
│   ├── notifications/
│   │   ├── whatsapp.py            # Notif a staff via Twilio WhatsApp
│   │   └── email.py
│   └── kb_ingestion/
│       ├── firecrawl.py           # Web crawl → Qdrant
│       └── pdf.py                 # PDF → LangChain → Qdrant
│
├── dashboard/                     # Panel de control del cliente
│   ├── api/                       # FastAPI endpoints
│   └── frontend/                  # UI (pendiente de definir tech)
│
├── docs/
│   ├── architecture.md            # Este archivo
│   └── verticals/
│       ├── clinica.md             # Documentación del vertical clínica
│       └── inmobiliaria.md
│
├── PLAN.md                        # Plan de acción por fases
└── README.md                      # Overview del proyecto
```

---

## Componentes core

### STT — Whisper (OpenAI)

```
Audio stream (Twilio) → chunks de 250ms → Whisper API → texto
```

- Whisper maneja acento argentino correctamente
- El gap de todo el repo awesome-llm-apps: ninguno integra STT de forma limpia
- Considerar Deepgram como alternativa si la latencia de Whisper es alta (< 300ms vs ~800ms)

### TTS — ElevenLabs

- Elegir voice model para ES-AR en Fase 0 (crítico: testear antes de comprometerse)
- Streaming de audio: no esperar a que el audio esté completo antes de reproducir
- `eleven_turbo_v2_5` — menor latencia que los modelos premium, suficiente calidad para voz telefónica

### RAG — Autonomous Pattern

```python
# Pseudocódigo del flujo de RAG
results = qdrant.search(query, collection="kb", score_threshold=0.75)

if results and results[0].score >= 0.75:
    context = results  # usa KB local
elif enable_web_fallback:
    context = web_search(query)  # fallback a web
    flag_uncertain = True  # marca que no es de la KB del cliente
else:
    return escalate_to_human()
```

### Memoria — Mem0 + Qdrant

- Mem0 usa Qdrant como vector store backend → un solo servicio para RAG y memoria
- Identificación: número de teléfono de Twilio (disponible en el webhook)
- Al iniciar llamada: `mem0.get_all(user_id=phone_number)` → contexto del paciente
- Al cerrar llamada: `mem0.add(messages=transcript, user_id=phone_number)`

### Orquestación — OpenAI Agents SDK

```python
# Patrón del ai_audio_tour_agent
orchestrator_agent = Agent(
    name="Recepcionista",
    instructions=persona_prompt,
    tools=[
        search_kb,
        check_availability,
        book_appointment,
        check_coverage,
        transfer_to_human,
    ]
)

# El orchestrator decide qué herramienta usar según la intención del usuario
# No necesita sub-agentes para el MVP — el doble-agente es para TTS, no para lógica
```

### Doble-agente para TTS

```
Agente 1 (Respuesta): Genera respuesta correcta y completa. Puede usar bullet points, datos precisos.
Agente 2 (TTS Optimizer): Convierte la respuesta en texto natural para hablar.
  - Elimina markdown, bullets, números con puntos
  - Frases < 20 palabras
  - Sin "a continuación", "por ende", "cabe destacar"
  - Añade conectores naturales del habla argentina
```

---

## Vertical Adapter — Cómo agregar un nuevo vertical

1. Copiar `verticals/template/` a `verticals/nuevo_vertical/`
2. Completar los 6 archivos de configuración
3. Crear KB sources y ejecutar ingesta
4. Testear con llamadas de prueba
5. Deploy

**Tiempo estimado: 1 día para un vertical con KB simple.**

---

## Decisiones de arquitectura

### ADR-001: ElevenLabs sobre OpenAI TTS

**Contexto:** El diferenciador del producto es la naturalidad de la voz en español rioplatense.
**Decisión:** ElevenLabs como proveedor de TTS principal.
**Consecuencia:** Costo algo mayor por minuto, pero calidad significativamente mejor para ES-AR. OpenAI TTS queda como fallback si ElevenLabs tiene downtime.

### ADR-002: Un solo Qdrant para RAG + Memoria

**Contexto:** Mem0 soporta Qdrant como vector store backend.
**Decisión:** Usar la misma instancia de Qdrant con colecciones separadas: `kb` (RAG) y `memory` (Mem0).
**Consecuencia:** Menor infra a mantener, mismo costo. No hay ganancia de performance en separar.

### ADR-003: Whisper sobre ElevenLabs STT

**Contexto:** ElevenLabs ofrece STT propio, pero Whisper tiene mejor soporte de ES-AR.
**Decisión:** Whisper (OpenAI) para STT.
**Consecuencia:** Latencia a monitorear (~300-800ms). Evaluar Deepgram como alternativa si supera 500ms P50.

### ADR-004: APIs externas en MVP, Unsloth en escala

**Contexto:** Fine-tuning de LLM y TTS daría mayor moat, pero ralentiza el MVP.
**Decisión:** APIs (OpenAI/Anthropic + ElevenLabs) para el MVP. Unsloth en Fase 3+ post-validación de mercado.
**Consecuencia:** Costo por minuto más alto en MVP, pero lanzamos en semanas no meses.

### ADR-005: Vertical Adapter Pattern desde el día uno

**Contexto:** El objetivo es construir una plataforma, no un producto de un solo cliente.
**Decisión:** Toda configuración vertical-específica en YAML desde la primera línea de código.
**Consecuencia:** El core es más abstracto (más esfuerzo inicial), pero escalar a nuevos verticales no requiere ingeniería.

---

## Latencia — objetivo y componentes

| Componente | Latencia objetivo | Notas |
|------------|------------------|-------|
| Twilio audio → server | ~50ms | WebSocket |
| Whisper STT | ~300-500ms | API call, depende de longitud |
| RAG retrieval (Qdrant) | ~50-100ms | Cloud, mismo región |
| LLM (GPT-4o / Claude) | ~400-800ms | Streaming desde primer token |
| TTS optimizer | ~200-400ms | Agente pequeño, prompt corto |
| ElevenLabs TTS | ~300-500ms | Streaming de audio |
| **Total P50** | **~1.2-1.5s** | |
| **Total P95** | **< 2.0s** | |

El streaming de TTS es crítico: el usuario tiene que escuchar el principio de la respuesta mientras el resto se genera.
