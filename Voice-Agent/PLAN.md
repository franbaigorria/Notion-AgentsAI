# Plan de Acción — Agente de Voz para Clínicas

> Primer vertical: clínicas y consultorios privados en Argentina.
> Arquitectura diseñada desde el día uno para adaptarse a cualquier vertical con mínimo esfuerzo.

---

## Contexto y decisiones tomadas

### Por qué clínicas

- Buenos Aires sola procesa ~40.000 turnos médicos por día
- Una recepcionista full-time cuesta ~USD 400-500/mes (dólar blue con cargas sociales)
- El agente de voz, a $0.25/min × 4min promedio × 50 llamadas/día = ~USD 1.500/mes con disponibilidad 24/7
- ROI obvio para el cliente, conversación compleja para nosotros (especialidad + cobertura + disponibilidad + obras sociales)
- Sin competidor dominante en Argentina todavía — Fonema AI es el más cercano pero es pan-LATAM desde México

### Canal inicial: LiveKit real-time voice (reemplazó a Twilio)

- LiveKit Agents da un pipeline de voz real-time (STT→LLM→TTS) con latencia sub-300ms
- WebRTC nativo — el audio viaja por streams, no por webhooks
- Twilio queda como opción futura para telefonía PSTN (SIP trunk → LiveKit)
- WhatsApp y web widget se agregan después con el mismo core

### Modelo de negocio: por minuto

- El cliente paga solo lo que usa
- Sin riesgo de suscripción cara con poco volumen al principio
- Fácil de calcular ROI vs. recepcionista humana
- Estrategia de precio puede cambiar según aprendizaje (freemium, bundle, etc.)

### Arquitectura: Vertical Adapter Pattern

El core del agente es idéntico para cualquier vertical.
Lo que cambia por vertical es una capa de configuración:
- Persona del agente (nombre, voz, personalidad)
- Knowledge base (fuente de datos: web crawl, PDFs, API del sistema)
- Conversation flows (cómo se comporta para este caso de uso)
- Integraciones (calendario, CRM, WhatsApp, etc.)
- Reglas de escalación (cuándo y cómo pasa a humano)

Esto permite lanzar un nuevo vertical en días, no semanas.

---

## Stack técnico (actualizado: refleja lo que está en producción)

| Capa | Tecnología | Estado |
|------|------------|--------|
| Voice framework | LiveKit Agents 1.x (WebRTC) | ✅ Producción en Railway US-East |
| **Modo Pipeline** | STT → LLM → TTS | ✅ Producción |
| ↳ STT | Deepgram Nova-3 (streaming) | ✅ Producción |
| ↳ LLM | GPT-4o-mini (OpenAI) — ganador del benchmark | ✅ Producción |
| ↳ TTS | ElevenLabs flash v2_5 (voz custom AR) | ✅ Producción |
| ↳ VAD | Silero VAD | ✅ Producción |
| **Modo Realtime** | gpt-4o-mini-realtime-preview (speech-to-speech) | ✅ Integrado, en evaluación |
| Toggle entre modos | `mode: pipeline \| realtime` en config.yaml | ✅ Implementado |
| Providers alternativos | Groq, Llama, Claude, Cartesia, Deepgram Aura | 🔬 Evaluados |
| Hosting | Railway US-East (Docker, uv) | ✅ Producción |
| Vector DB | Qdrant Cloud | 🔜 Fase 2 Track B |
| Embeddings | FastEmbed | 🔜 Fase 2 Track B |
| Ingesta de KB | Firecrawl (web) + LangChain (PDFs) | 🔜 Fase 2 Track B |
| Tools / function calling | Compartido por ambos modos | 🔜 Fase 2 Track B |
| Memoria entre sesiones | Mem0 + Qdrant | 🔜 Fase 4 |
| Backend API | FastAPI (cuando haga falta dashboard) | 🔜 Fase 7 |

### Por qué este stack y no otro

- **LiveKit Agents sobre Twilio webhooks**: pipeline nativo de voz real-time con preemptive generation. Twilio requería STT→webhook→LLM→TTS→webhook — mucha latencia. LiveKit hace todo en-process.
- **Groq LPU sobre GPT-4o/Claude para conversación**: ~100ms TTFT. Para la capa conversacional (fillers, respuestas rápidas) la velocidad es todo. La inteligencia pesada la pone o4-mini en la capa de razonamiento.
- **Deepgram Nova-3 sobre Whisper**: streaming nativo, mejor latencia para real-time. Whisper es batch.
- **ElevenLabs sobre otros TTS**: mejor naturalidad en español rioplatense después de testear Cartesia y Deepgram Aura.
- **Railway US-East**: co-localizar el worker con LiveKit Cloud y los providers de API redujo E2E de ~1500ms a ~250ms. La latencia de red desde Argentina era el cuello de botella.
- **Patrón multi-agente (Fase 2)**: Llama (rápido, filler) + o4-mini (inteligente, RAG) — el usuario nunca espera en silencio.
- **Unsloth**: reservado para post-validación. Fine-tuning de LLM y TTS para bajar costos. No tocar en MVP.

---

## Fases del MVP

### Fase 0 — Cimientos ✅ COMPLETADA

**Objetivo:** entorno funcionando, sin una línea de producto todavía.

**Lo que se hizo:**
- [x] Repositorio con estructura base (`core/`, `verticals/`, `adapters/`, `dashboard/`, `tests/`)
- [x] Setup ElevenLabs: voz argentina custom elegida y testeada (`7FWgFcfrZ8cVdbfxtLKk`)
- [x] Setup Deepgram: API key, STT Nova-3 configurado
- [x] Setup Groq: API key, Llama 3.1 8B Instant como LLM principal
- [x] Setup Anthropic + OpenAI: keys configuradas como providers alternativos
- [x] Vertical Adapter Pattern: `verticals/clinica/config.yaml` + `persona.md`
- [x] `env.example` con todas las variables
- [x] Dockerfile para deploy en Railway

**Cambios vs plan original:** Twilio reemplazado por LiveKit. FastAPI no fue necesario — LiveKit Agents maneja el pipeline directamente. Qdrant y Firecrawl se mueven a Fase 2 (RAG).

---

### Fase 1 — Loop de voz central ✅ COMPLETADA

**Objetivo:** la conversación de voz funciona end-to-end, sin RAG todavía.

**Flujo implementado:**
```
LiveKit Room (WebRTC)
  → Silero VAD (detección de voz)
  → Deepgram Nova-3 STT (streaming)
  → Groq LPU / Llama 3.1 8B (respuesta rápida)
  → ElevenLabs TTS (voz argentina custom)
  → LiveKit → audio al usuario
  → [loop con preemptive_generation=True]
```

**Lo que se hizo:**
- [x] Pipeline LiveKit Agents: VAD → STT → LLM → TTS con preemptive generation
- [x] Persona y prompt optimizados para voz masculina argentina neutra
- [x] Múltiples providers testeados: STT (Deepgram), LLM (Claude, OpenAI, Groq, Ollama), TTS (ElevenLabs, Cartesia, Deepgram Aura)
- [x] Métricas de LiveKit: TTFT, TTFB, EOU delay logueados por turno
- [x] Deploy en Railway US-East: E2E ~250ms (objetivo original era <1.5s)
- [x] Manejo de silencio e interrupciones via Silero VAD

**Métricas alcanzadas (superaron el objetivo):**
- Latencia E2E ~250ms (objetivo era P50 < 1.2s) — **5x mejor que el target**
- La voz suena natural con ElevenLabs custom
- Preemptive generation elimina gaps entre turnos

---

### Fase 2 — Voz natural + Arquitectura dual (actual)

**Objetivo:** el agente suena humano (no robótico) Y conoce la clínica. **Dos arquitecturas coexistiendo** + RAG.

---

#### Estrategia: dual-mode architecture

Decisión arquitectónica tomada en esta fase: **soportar dos modos de operación** seleccionables por config para ofrecer un servicio adaptado al cliente.

```yaml
# verticals/<vertical>/config.yaml
mode: pipeline   # o: realtime
```

| Modo | Stack | Ideal para |
|------|-------|------------|
| **`pipeline`** | Deepgram STT + GPT-4o-mini + ElevenLabs TTS custom | Clínicas argentinas, negocios locales — donde la voz nativa AR es diferenciador |
| **`realtime`** | OpenAI gpt-4o-mini-realtime (speech-to-speech) | B2B, soporte técnico, casos donde velocidad > acento |

**Latencia comparada (medida en producción):**
- Pipeline: ~1.3s E2E (EOU 0.55 + STT 0.30 + LLM 0.35 + TTS 0.15)
- Realtime: ~0.5s E2E (server-side VAD + TTFT 0.50)

**Costo comparado:**
- Pipeline: ~$0.05/min
- Realtime: ~$0.08-0.12/min

Ambos modos comparten:
- Mismo persona.md (instrucciones del agente)
- Mismas herramientas de RAG (tools)
- Misma estructura de vertical adapter

Solo cambia QUIÉN ejecuta el loop conversacional.

---

#### Track A: Voz natural — argentino neutro

**Problema:** la voz funciona pero puede sonar artificial en entonación, ritmo, o elección de palabras. Queremos que la experiencia sea agradable — que el paciente no sienta que habla con un bot.

**Tareas:**
- [ ] Tuning de ElevenLabs: ajustar stability, similarity_boost, style en la voz custom
- [ ] Experimentar con voice settings por tipo de respuesta (saludo vs. info técnica vs. filler)
- [ ] Optimizar persona.md: frases más cortas, ritmo conversacional, muletillas naturales ("mirá", "dale", "perfecto")
- [ ] Testear output de Llama 3.1 para voz: que no genere markdown, bullets, ni frases largas
- [ ] A/B entre ElevenLabs Multilingual v2 y Turbo v2.5 (menor latencia, ¿suficiente calidad?)
- [ ] Definir criterios subjetivos de calidad: grabar 10 conversaciones, evaluar naturalidad 1-10

**Entregable:** la voz suena a recepcionista real, no a asistente virtual.

---

#### Track B: RAG vía tools (unificado para ambos modos)

**Problema:** cuando el paciente pregunta algo que requiere buscar (especialidades, horarios, cobertura), el agente necesita acceder a la KB de la clínica. Sin RAG, inventa o dice "no sé".

**Arquitectura (misma herramienta, dos modos de ejecución):**

```python
@function_tool
async def search_clinica_kb(query: str) -> str:
    """Busca info en la base de conocimiento de la clínica.

    El modelo llama esta función cuando detecta que necesita datos
    específicos (especialidades, médicos, cobertura, horarios).
    """
    # Qdrant + FastEmbed → retrieved context
    return context
```

**En modo `pipeline`:** GPT-4o-mini llama la tool cuando lo considera necesario. LiveKit Agents orquesta el tool-call round-trip.

**En modo `realtime`:** gpt-4o-mini-realtime llama la tool nativamente — puede empezar a decir "dejame chequear eso..." en audio MIENTRAS la tool se ejecuta en paralelo. Todo en un solo modelo.

**Por qué este diseño > multi-agente (la arquitectura anterior propuesta):**

El plan original proponía un patrón "Llama filler + o4-mini RAG + Llama reformula". Esa complejidad venía de LIMITACIONES que ya no aplican:
- Llama 3.1 8B era rápido pero flojo en español AR → reemplazado por GPT-4o-mini (mejor naturalidad)
- La latencia de o4-mini obligaba a usar fillers → ya no son necesarios con Realtime o pipeline bien tuneado
- Coordinar 2 modelos genera fallback paths complejos → tool calling nativo es simpler

Nueva regla: **un solo modelo por request** (sea pipeline LLM o Realtime), con tools para acceso a data externa.

**Fuentes de ingesta de KB (en orden de complejidad):**
1. Web crawl del sitio de la clínica con Firecrawl
2. PDFs (listado de médicos, aranceles, cobertura por obra social)
3. Datos estructurados via API (si la clínica tiene sistema, ej: Docplanner)

**Tareas:**
- [ ] Diseñar orquestación custom sobre LiveKit AgentSession (override del pipeline lineal)
- [ ] Implementar router en Llama: clasificar intent → respuesta directa vs. RAG
- [ ] Implementar filler generation: Llama genera acknowledgment mientras o4-mini trabaja
- [ ] Pipeline de ingesta: Firecrawl → FastEmbed → Qdrant (colección `kb`)
- [ ] Retrieval con scoring de relevancia desde o4-mini
- [ ] Prompt de o4-mini: "Respondé SOLO con info del contexto. Si no está, decí que no la tenés."
- [ ] Prompt de Llama (reformulación): "Reformulá para voz hablada. Frases cortas. Sin markdown."
- [ ] Guardrails anti-alucinación: si el retrieved context no contiene la info → "no tengo esa información, ¿querés que te pase con alguien?"
- [ ] Manejo de estado conversacional entre ambos modelos (historial compartido)
- [ ] Tests E2E: preguntas con RAG, preguntas sin RAG, preguntas sin respuesta en KB

**Entregable:** el agente puede responder el 90%+ de preguntas frecuentes de una clínica real, sin silencios incómodos, con voz natural.

**Métricas de aceptación:**
- Tiempo hasta primer audio (filler): < 500ms
- Tiempo hasta respuesta completa (con RAG): < 3s
- Precisión de respuestas RAG: > 90% en preguntas de test
- Tasa de alucinación: < 2%
- Naturalidad percibida de la voz: > 7/10 en evaluación subjetiva

---

### Fase 3 — Lógica específica de clínicas (Semana 4-5)

**Objetivo:** el agente hace lo que hace la recepcionista. Saca turnos, verifica cobertura, confirma horarios.

**Flows de conversación:**
1. **Agendar turno**: detecta especialidad → verifica disponibilidad → agenda → confirma por SMS (Twilio)
2. **Consulta de cobertura**: detecta obra social + plan → busca en KB de coberturas → responde con certeza o deriva
3. **Info general**: cómo llegar, horario de atención, teléfono directo, estacionamiento
4. **Reagendar/cancelar turno**: busca el turno del paciente → modifica → confirma

**Integración con sistema de turnos:**
- Si la clínica tiene Docplanner/Medicloud/sistema propio: API adapter
- Si no tiene sistema: Google Calendar como fallback (fácil de integrar, el cliente ya lo tiene)

**Obras sociales argentinas — KB prioritaria:**
- OSDE (planes 210, 310, 410, 510, 610)
- Swiss Medical
- Galeno
- IOMA
- PAMI / PAMI Médica
- Medicus
- Jerárquicos

**Tareas:**
- [ ] Conversation state machine: detecta intención → ejecuta flow → confirma → cierra
- [ ] Integración con Google Calendar (primer sistema de turnos)
- [ ] Adapter para Docplanner API (si el cliente lo usa)
- [ ] KB de coberturas por obra social (manual primero, luego automatizado)
- [ ] Confirmación de turno por SMS via Twilio
- [ ] Tests de conversación end-to-end para los 4 flows

**Entregable:** una clínica beta puede reemplazar el 80% de sus llamadas entrantes con el agente.

---

### Fase 4 — Memoria entre sesiones (Semana 5-6)

**Objetivo:** el agente recuerda al paciente. "La última vez que llamaste pediste turno con el Dr. García..."

**Patrón de referencia:** `llm_app_personalized_memory` (Mem0 + Qdrant)

**Datos que se recuerdan por paciente:**
- Última especialidad consultada
- Obra social y plan
- Médico de cabecera o preferido
- Si tiene turno próximo (para no sacar otro)
- Nombre (si se presentó en llamada anterior)

**Implementación:**
- Identificación del paciente por número de teléfono (Twilio lo da automáticamente)
- Mem0 → guarda/recupera memoria del paciente en Qdrant (colección `memory`)
- Mismo Qdrant para RAG + memoria: un solo servicio

**Tareas:**
- [ ] Integrar Mem0 con Qdrant colección `memory`
- [ ] Al inicio de cada llamada: recuperar memoria del número entrante
- [ ] Al final de cada llamada: guardar hechos relevantes de la conversación
- [ ] Prompt actualizado: usa la memoria para personalizar la respuesta

**Entregable:** el agente recuerda al paciente en llamadas subsiguientes y la conversación se siente personal.

---

### Fase 5 — Handoff a humano (Semana 6)

**Objetivo:** cuando el agente no puede, pasa a un humano de forma elegante. Nunca deja al paciente tirado.

**Reglas de escalación (configurables por vertical):**
- El paciente pide explícitamente hablar con una persona
- El agente no pudo resolver el problema en 3 intentos
- El tema detectado está fuera del scope del agente (emergencias, prescripciones, resultados)
- Nivel de incertidumbre del retrieved context < threshold

**Mecanismo:**
```
Trigger de escalación detectado
  → Agente: "Voy a pasarte con alguien del equipo, un momento."
  → Notificación a staff (WhatsApp/email/SMS con resumen de la conversación)
  → Twilio: transfer de llamada al número del staff
  → Si no atiende en N segundos: buzón de voz + callback automático
```

**Tareas:**
- [ ] Detector de intención de escalación (prompt-based + reglas explícitas)
- [ ] Transfer de llamada via Twilio API
- [ ] Resumen automático de la conversación para el humano receptor
- [ ] Notificación a staff (WhatsApp via Twilio o email)
- [ ] Fallback: buzón de voz + SMS de callback

**Entregable:** el agente escala graciosamente y el staff recibe un resumen antes de contestar.

---

### Fase 6 — Vertical Adapter (Semana 7-8)

**Objetivo:** demostrar que el mismo core funciona en otro vertical. Target: inmobiliaria.

**Por qué inmobiliaria como prueba:**
- El dolor es real (67% de consultas fuera de horario)
- El ciclo de venta es el más rápido (dueño decide solo)
- Puede ser el primer cliente real que pague mientras terminamos clínicas
- La conversación es diferente en estructura → prueba que el Adapter Pattern funciona

**Estructura del Vertical Adapter:**
```
verticals/
  clinica/
    config.yaml          # nombre del agente, voz, idioma, reglas
    persona.md           # cómo habla, qué puede y no puede hacer
    flows.yaml           # lista de conversation flows
    kb_sources.yaml      # de dónde ingesta la KB (URLs, PDFs, APIs)
    integrations.yaml    # qué conectores activa (calendar, CRM, etc.)
    escalation_rules.yaml # cuándo y cómo escala a humano
  inmobiliaria/
    config.yaml
    persona.md
    flows.yaml
    kb_sources.yaml
    integrations.yaml
    escalation_rules.yaml
  template/              # template para un nuevo vertical en blanco
    ...
```

**Tareas:**
- [ ] Abstraer toda configuración vertical-específica en los 6 archivos de config
- [ ] Core del agente: lee la config del vertical al inicio, no tiene lógica hardcodeada
- [ ] Crear config de inmobiliaria: flows de consulta de propiedades + agendado de visita + pre-calificación de lead
- [ ] Probar que cambiar de `clinica/` a `inmobiliaria/` no requiere tocar el core
- [ ] Documentar cómo agregar un nuevo vertical en < 1 día

**Entregable:** el mismo agente atiende llamadas de clínica y de inmobiliaria, configurado solo con YAML.

---

### Fase 7 — Dashboard y facturación (Semana 8-10)

**Objetivo:** el cliente puede ver qué está pasando y nosotros podemos cobrar.

**Dashboard del cliente (MVP):**
- Log de llamadas: fecha, duración, número, resumen de la conversación
- Transcripciones completas
- Tasa de resolución vs. escalación a humano
- Minutos consumidos en el período
- Factura del período

**Facturación:**
- Contador de minutos por cliente (Twilio da el dato)
- Rate configurable por cliente
- Invoice automático (Stripe o manual al principio)

**Tareas:**
- [ ] Backend: endpoint de logs de llamadas
- [ ] Transcripción guardada en DB post-llamada
- [ ] Resumen automático de cada llamada (LLM en batch, no en tiempo real)
- [ ] Frontend simple: tabla de llamadas + transcripción + métricas
- [ ] Contador de minutos + factura en PDF

**Entregable:** el cliente puede logearse, ver sus llamadas, y nosotros podemos enviarle una factura.

---

## Métricas de éxito del MVP

| Métrica | Target | Actual (Fase 1) |
|---------|--------|-----------------|
| Latencia E2E (respuesta directa) | < 500ms | ~250ms ✅ |
| Latencia E2E (con RAG, incluye filler) | < 3s | 🔜 Fase 2 |
| Tiempo hasta primer audio (filler) | < 500ms | 🔜 Fase 2 |
| Tasa de resolución sin humano | > 80% | 🔜 Fase 3 |
| Tasa de alucinación / respuesta incorrecta | < 2% | 🔜 Fase 2 |
| NPS del paciente que usó el agente | > 7/10 | 🔜 Beta |
| Costo por minuto de conversación | < USD 0.15 | Por medir |

---

## Roadmap visual

```
✅ DONE    │ Fase 0: Cimientos (repo, providers, Railway deploy)
✅ DONE    │ Fase 1: Loop de voz (E2E ~250ms, 5x mejor que target)
 ► ACTUAL  │ Fase 2: Voz natural + Arquitectura dual + RAG vía tools
           │   ├─ Track A: TTS tuning + persona con ejemplos AR ✅ (en iteración)
           │   ├─ Track B: RAG vía function tools (Qdrant + Firecrawl)
           │   └─ Dual-mode: pipeline vs realtime, toggle por config ✅
           │ Fase 3: Flows de clínica (turnos, cobertura, info)
           │ Fase 4: Memoria entre sesiones (Mem0)
           │ Fase 5: Handoff a humano
           │ Fase 6: Vertical Adapter (inmobiliaria como prueba)
           │ Fase 7: Dashboard + facturación
           │
           ▼ Beta con cliente real de clínica → primer ingreso
           ▼ Beta con cliente B2B → validar modo realtime
```

---

## Lo que NO hacemos en el MVP

- Fine-tuning de LLM o TTS (Unsloth está reservado para escala, post-validación)
- WhatsApp y web widget (voz primero, otros canales después)
- Integración con sistemas de historia clínica (HIS/EMR)
- Cierre de ventas complejas
- Soporte multilingüe
- Modelo de IA propio (usamos APIs)
- Memoria entre sesiones (Fase 4 — primero que sepa de la clínica, después que recuerde pacientes)

---

## Referencias técnicas

| Patrón | Referencia | Aplicación en nuestro stack |
|--------|-----------|----------------------------|
| RAG sobre KB de cliente con Qdrant + Firecrawl | `customer_support_voice_agent` | Fase 2 Track B: ingesta de KB de la clínica |
| Multi-agent: filler + background reasoning | Retell AI, Vapi (patrón de producción) | Fase 2 Track B: Llama filler + o4-mini RAG |
| Doble-agente para optimizar respuesta para TTS | `voice_rag_openaisdk` | Fase 2: Llama reformula output de o4-mini para voz |
| Memoria persistente con Mem0 + Qdrant | `llm_app_personalized_memory` | Fase 4: reconocimiento de pacientes |
| RAG con fallback a web search | `autonomous_rag` | Fase 2: cuando KB local no tiene la info |
| Corrective RAG (CRAG) | `corrective_rag` | Post-MVP: reducir errores en respuestas críticas |
| LiveKit Agents pipeline customization | LiveKit docs | Fase 2: override de pipeline lineal para multi-agent |

---

## Próximo paso inmediato

Arrancar la Fase 2, dos tracks en paralelo:

**Track A (Voz):** experimentar con voice settings de ElevenLabs y optimizar el persona.md para que el output de Llama sea naturalmente "hablable". Esto es iterativo — grabar, escuchar, ajustar.

**Track B (Multi-Agent RAG):** diseñar la orquestación custom sobre LiveKit AgentSession. El primer paso concreto es implementar el router de intents en Llama (¿respuesta directa o necesita RAG?) y el mecanismo de filler + respuesta diferida. Una vez que eso funcione, conectar la pipeline de ingesta (Firecrawl → FastEmbed → Qdrant) y el razonamiento con o4-mini.
