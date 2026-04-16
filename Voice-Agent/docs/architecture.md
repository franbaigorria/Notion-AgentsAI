# Arquitectura Técnica — Voice Agent Platform

## Principio de diseño

El agente de voz es una **plataforma multi-tenant** con un core invariante y dos capas de configuración:

| Concepto | Qué es | Dónde vive |
|----------|--------|------------|
| **Vertical** | Template de industria (clínica, inmobiliaria, etc.) | Repo — `verticals/{vertical}/` |
| **Tenant** | Cliente real que usa la plataforma | Base de datos externa |

Un vertical es una plantilla reutilizable. Un tenant es un cliente concreto que instancia esa plantilla con su nombre, voz, KB y sistemas de integración propios.

**Regla crítica:** el aislamiento de datos es por `tenant_id`, no por `vertical`. Dos clínicas distintas son dos tenants distintos — su KB, memoria e integraciones son completamente independientes aunque compartan el mismo template.

El core nunca cambia por tenant. Agregar un nuevo cliente es operación de datos, no de ingeniería.

---

## Diagrama de flujo principal

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LLAMADA ENTRANTE                             │
│                         (Twilio webhook)                            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  phone_number (del webhook)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ROUTING POR TENANT                             │
│  TelephonyRouter.lookup(phone_number) → tenant_id                   │
│  load_tenant(tenant_id):                                            │
│    - DB fetch: config del tenant (nombre, voz, vertical)            │
│    - template merge: verticals/{vertical}/ (persona, flows)         │
│    - instancia los 3 providers del tenant                           │
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
│  │              3 CAPAS DE DATOS (por tenant_id)              │    │
│  │                                                            │    │
│  │  KnowledgeProvider.retrieve(query, tenant_id)             │    │
│  │    → Qdrant[kb_{tenant_id}] con score de relevancia        │    │
│  │    → fallback: web search si score < threshold             │    │
│  │                                                            │    │
│  │  MemoryProvider.get(user_id, tenant_id)                   │    │
│  │    → historial de llamadas anteriores del usuario          │    │
│  │                                                            │    │
│  │  CapabilityProvider.execute(action, params, tenant_id)    │    │
│  │    → agendar turno, verificar cobertura, etc.              │    │
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
   │ MemoryProvider.save │         │ Resumen de conversación │
   │ (user_id, tenant_id │         │ Notificación a staff    │
   │  transcript)        │         │ Transfer Twilio         │
   └─────────────────────┘         └─────────────────────────┘
```

---

## Estructura del repositorio

```
voice-agent/
├── core/                          # El motor — NO cambia por tenant
│   ├── stt/                       # Whisper STT pipeline
│   ├── tts/                       # ElevenLabs TTS pipeline
│   ├── llm/                       # LLM client (Claude / GPT-4o)
│   ├── knowledge/                 # Knowledge Access — KnowledgeProvider (Port/Adapter)
│   ├── memory/                    # Memory Access — MemoryProvider (Port/Adapter)
│   ├── capabilities/              # Operational Access — CapabilityProvider (Port/Adapter)
│   ├── orchestrator/              # LiveKit Agents — orquesta los providers
│   ├── escalation/                # Detector de escalación + handoff
│   └── telephony/                 # Twilio webhook handler + stream
│
├── verticals/                     # Templates por industria (repo)
│   ├── clinica/
│   │   ├── config.yaml            # nombre, voz ElevenLabs, idioma, timezone
│   │   ├── persona.md             # cómo habla, qué puede/no puede hacer
│   │   ├── flows.yaml             # agendar turno, consulta cobertura, info, reagendar
│   │   ├── kb_sources.yaml        # URLs a crawlear, PDFs a ingestar, APIs a conectar
│   │   ├── integrations.yaml      # capabilities disponibles para este vertical
│   │   └── escalation_rules.yaml  # triggers de escalación + contacto del staff
│   │
│   └── template/                  # Plantilla vacía para un nuevo vertical
│
├── adapters/                      # Implementaciones concretas de los Ports
│   ├── knowledge/
│   │   ├── qdrant_knowledge.py    # KnowledgeProvider → Qdrant[kb_{tenant_id}]
│   │   └── web_knowledge.py       # KnowledgeProvider → búsqueda web (fallback)
│   ├── memory/
│   │   └── mem0_memory.py         # MemoryProvider → Mem0 + Qdrant[mem_{tenant_id}]
│   └── capabilities/
│       ├── google_calendar.py     # CapabilityProvider → Google Calendar del tenant
│       └── docplanner.py          # CapabilityProvider → Docplanner
│
├── docs/
│   └── architecture.md            # Este archivo
│
└── README.md
```

---

## Modelo Multi-Tenant

### Relación Vertical ↔ Tenant

```
vertical: "clinica"          (template en repo)
    │
    ├── tenant: "clinica_del_valle"   (cliente 1 — DB)
    │     ├── kb:  Qdrant[kb_clinica_del_valle]
    │     ├── mem: Qdrant[mem_clinica_del_valle]
    │     └── cap: Google Calendar de Clinica del Valle
    │
    └── tenant: "centro_medico_sur"  (cliente 2 — DB)
          ├── kb:  Qdrant[kb_centro_medico_sur]
          ├── mem: Qdrant[mem_centro_medico_sur]
          └── cap: Docplanner de Centro Médico Sur
```

### Onboarding de un nuevo tenant

| Paso | Acción | Sin ingeniería |
|------|--------|----------------|
| 1 | Crear registro en DB: `{tenant_id, vertical, voice_id, phone_number}` | ✅ |
| 2 | Ingestar KB del cliente → `kb_{tenant_id}` en Qdrant | ✅ |
| 3 | Configurar integración (Google Calendar, etc.) | ✅ |
| 4 | Mapear número de teléfono → `tenant_id` en TelephonyRouter | ✅ |

**Tiempo estimado: 1 día para un tenant con KB simple.**

---

## 3 Capas de Datos (Port/Adapter)

El core define 3 puertos (interfaces abstractas). Los adapters concretos viven en `adapters/`.

### Capa 1 — Knowledge Access (`core/knowledge/`)

Recupera información estática o semi-estructurada del negocio.
Ejemplos: coberturas, horarios, políticas, FAQs.

```python
class KnowledgeProvider(ABC):
    async def retrieve(self, query: str, tenant_id: str) -> KnowledgeResult: ...
    # Qdrant collection: kb_{tenant_id}
```

Flujo interno del adapter concreto:
```
query + tenant_id
  → Qdrant.search(collection="kb_{tenant_id}", score_threshold=0.75)
  → score >= 0.75 → KnowledgeResult(source="kb_local")
  → score < 0.75  → web fallback → KnowledgeResult(source="web")
  → sin resultado → KnowledgeResult(source="none") → flag de escalación
```

### Capa 2 — Memory Access (`core/memory/`)

Recuerda al usuario entre llamadas. Identificación por teléfono + tenant.

```python
class MemoryProvider(ABC):
    async def get(self, user_id: str, tenant_id: str) -> list[Memory]: ...
    async def save(self, user_id: str, tenant_id: str, transcript: str) -> None: ...
    # Mem0 namespace: mem_{tenant_id}
```

Un mismo número de teléfono que llama a dos tenants distintos tiene **memoria completamente separada**.

### Capa 3 — Operational Access / Capabilities (`core/capabilities/`)

Ejecuta acciones transaccionales en sistemas externos del tenant.
Ejemplos: agendar turno, verificar cobertura, actualizar CRM.

```python
class CapabilityProvider(ABC):
    @property @abstractmethod
    def name(self) -> str: ...          # nombre del tool para el LLM

    @property @abstractmethod
    def description(self) -> str: ...   # descripción para que el LLM decida cuándo usarlo

    @property @abstractmethod
    def parameters(self) -> dict: ...   # JSON Schema de los parámetros

    async def execute(self, action: str, params: dict, tenant_id: str) -> CapabilityResult: ...

    def as_livekit_tool(self) -> dict:  # concreto en base class
        """Construye el descriptor del tool para LiveKit AgentSession."""
        return {"name": self.name, "description": self.description, "parameters": self.parameters}
```

El orchestrator registra capabilities de la siguiente forma:
```python
tools = [cap.as_livekit_tool() for cap in tenant.capabilities]
```

---

## Componentes core

### STT — Whisper (OpenAI)

```
Audio stream (Twilio) → chunks de 250ms → Whisper API → texto
```

- Whisper maneja acento argentino correctamente
- Evaluar Deepgram como alternativa si latencia supera 500ms P50

### TTS — ElevenLabs

- `eleven_turbo_v2_5` — menor latencia, suficiente calidad para voz telefónica
- Streaming de audio: no esperar a que el audio esté completo antes de reproducir

### Orquestación — LiveKit Agents

```python
session = AgentSession(
    instructions=tenant.persona_prompt,
    tools=[cap.as_livekit_tool() for cap in tenant.capabilities],
)
```

### Doble-agente para TTS

```
Agente 1 (Respuesta): genera respuesta correcta y completa
Agente 2 (TTS Optimizer): convierte a texto natural para hablar
  - Elimina markdown, bullets, números con puntos
  - Frases < 20 palabras
  - Sin "a continuación", "por ende", "cabe destacar"
  - Añade conectores naturales del habla argentina
```

---

## Decisiones de arquitectura

### ADR-001: ElevenLabs sobre OpenAI TTS

**Contexto:** El diferenciador del producto es la naturalidad de la voz en español rioplatense.
**Decisión:** ElevenLabs como proveedor de TTS principal.
**Consecuencia:** Costo algo mayor por minuto, pero calidad significativamente mejor para ES-AR. OpenAI TTS queda como fallback.

### ADR-002: Un solo Qdrant para Knowledge + Memory

**Contexto:** Mem0 soporta Qdrant como vector store backend.
**Decisión:** Misma instancia de Qdrant con colecciones separadas por tenant: `kb_{tenant_id}` y `mem_{tenant_id}`.
**Consecuencia:** Menor infra a mantener. El naming por tenant garantiza aislamiento sin filtros en query.

### ADR-003: Whisper sobre ElevenLabs STT

**Contexto:** ElevenLabs ofrece STT propio, pero Whisper tiene mejor soporte de ES-AR.
**Decisión:** Whisper (OpenAI) para STT.
**Consecuencia:** Latencia a monitorear (~300-800ms). Evaluar Deepgram si supera 500ms P50.

### ADR-004: APIs externas en MVP, fine-tuning en escala

**Contexto:** Fine-tuning de LLM y TTS daría mayor moat, pero ralentiza el MVP.
**Decisión:** APIs (OpenAI/Anthropic + ElevenLabs) para el MVP.
**Consecuencia:** Costo por minuto más alto en MVP, pero lanzamos en semanas no meses.

### ADR-005: Vertical Adapter Pattern desde el día uno

**Contexto:** El objetivo es construir una plataforma, no un producto de un solo cliente.
**Decisión:** Toda configuración vertical-específica en YAML desde la primera línea de código.
**Consecuencia:** El core es más abstracto, pero escalar a nuevos verticales no requiere ingeniería.

### ADR-006: Aislamiento por tenant_id, no por vertical

**Contexto:** La unidad de negocio real es el tenant (cliente), no el vertical (industria). Dos clínicas son dos tenants distintos — sus datos no deben mezclarse aunque usen el mismo template.
**Decisión:** `tenant_id` como clave de aislamiento en todos los providers (Knowledge, Memory, Capabilities). `vertical` solo identifica qué template usar.
**Consecuencia:** Onboarding de nuevos clientes es operación de datos. No hay código que cambiar.

### ADR-007: Port/Adapter pattern para las 3 capas de datos

**Contexto:** Knowledge, Memory y Capabilities van a tener múltiples implementaciones (Qdrant, Mem0, Google Calendar, Docplanner, etc.). El core no puede depender de ninguna concreta.
**Decisión:** ABCs en `core/{knowledge,memory,capabilities}/base.py`. Implementaciones concretas en `adapters/`. El orchestrator trabaja solo con las interfaces.
**Consecuencia:** Swappear un provider es cambiar qué clase se instancia — sin tocar el core. Testing con stubs sin infraestructura real.

---

## Latencia — objetivo y componentes

| Componente | Latencia objetivo | Notas |
|------------|------------------|-------|
| Twilio audio → server | ~50ms | WebSocket |
| Whisper STT | ~300-500ms | depende de longitud del utterance |
| Knowledge retrieval (Qdrant) | ~50-100ms | Cloud, misma región |
| LLM (GPT-4o / Claude) | ~400-800ms | Streaming desde primer token |
| TTS optimizer | ~200-400ms | Agente pequeño, prompt corto |
| ElevenLabs TTS | ~300-500ms | Streaming de audio |
| **Total P50** | **~1.2-1.5s** | |
| **Total P95** | **< 2.0s** | |

El streaming de TTS es crítico: el usuario tiene que escuchar el principio de la respuesta mientras el resto se genera.
