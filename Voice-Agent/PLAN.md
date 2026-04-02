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

### Canal inicial: llamada telefónica (Twilio)

- El canal más limpio para un voice agent puro
- WhatsApp y web widget se agregan después con el mismo core
- Twilio da número local argentino, webhook de entrada, y TTS/STT nativos si necesitamos fallback

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

## Stack técnico

| Capa | Tecnología | Referencia de arquitectura |
|------|------------|---------------------------|
| Telefonía | Twilio (número local AR) | — |
| STT | Whisper (OpenAI API) | Gap no resuelto en awesome-llm-apps |
| LLM | Claude Sonnet / GPT-4o | Según latencia y costo en producción |
| TTS | ElevenLabs (acento argentino) | Mejor calidad de voz para ES-AR |
| Vector DB | Qdrant Cloud | customer_support_voice_agent + llm_app_personalized_memory |
| Embeddings | FastEmbed | customer_support_voice_agent |
| Ingesta de KB | Firecrawl (web) + LangChain (PDFs) | customer_support_voice_agent + voice_rag_openaisdk |
| Memoria entre sesiones | Mem0 + Qdrant (misma instancia) | llm_app_personalized_memory |
| RAG routing | Autonomous RAG pattern | autonomous_rag |
| Orquestación multi-agente | OpenAI Agents SDK | ai_audio_tour_agent |
| Backend | FastAPI (Python) | — |
| Optimización de respuesta para TTS | Doble-agente (respuesta → optimización para voz) | voice_rag_openaisdk |

### Por qué este stack y no otro

- **ElevenLabs sobre OpenAI TTS**: mejor naturalidad en español rioplatense. Es bloqueante para el producto.
- **Qdrant para RAG + Mem0**: Mem0 usa Qdrant como backend de vector store — un solo servicio para dos funciones.
- **FastEmbed**: embeddings locales, sin costo por llamada a API de embeddings.
- **Autonomous RAG**: cuando el cliente no tiene la info en su KB, el agente busca en web antes de decir "no sé".
- **Doble-agente para TTS**: el primer agente genera la respuesta correcta; el segundo la reformula para que suene natural hablada (sin bullets, sin markdown, frases cortas). Patrón del voice_rag_openaisdk.
- **Unsloth**: reservado para Fase 3+ cuando haya validación de mercado. Fine-tuning de LLM y TTS para bajar costos y mejorar el moat. No tocar en MVP.

---

## Fases del MVP

### Fase 0 — Cimientos (Semana 1)

**Objetivo:** entorno funcionando, sin una línea de producto todavía.

**Tareas:**
- [ ] Crear repositorio con estructura base (monorepo: `core/`, `verticals/`, `adapters/`, `dashboard/`)
- [ ] Setup Twilio: número argentino, webhook configurado
- [ ] Setup Qdrant Cloud: instancia con colecciones `kb` y `memory`
- [ ] Setup ElevenLabs: voz argentina elegida y testeada
- [ ] Setup OpenAI/Anthropic: keys, rate limits, costs estimados por conversación
- [ ] Firecrawl: cuenta y primer crawl de prueba
- [ ] FastAPI skeleton: health check, webhook de Twilio, estructura de rutas
- [ ] `.env.example` con todas las variables necesarias

**Entregable:** llamar al número de Twilio → escuchar "Hola, soy [nombre del agente]" con voz de ElevenLabs.

---

### Fase 1 — Loop de voz central (Semana 2-3)

**Objetivo:** la conversación de voz funciona end-to-end, sin RAG todavía.

**Flujo completo:**
```
Llamada entrante (Twilio)
  → Whisper STT → texto del usuario
  → GPT-4o / Claude → respuesta
  → Agente optimizador → respuesta reformulada para voz
  → ElevenLabs TTS → audio
  → Twilio → reproduce al llamante
  → [loop hasta que cuelga]
```

**Tareas:**
- [ ] Webhook de Twilio → stream de audio → Whisper STT
- [ ] Prompt base del agente (personalidad, idioma, reglas de comportamiento)
- [ ] Pipeline LLM → doble-agente (respuesta + optimización para TTS)
- [ ] ElevenLabs TTS → stream de audio de vuelta a Twilio
- [ ] Manejo de silencio, interrupciones y cuelgue
- [ ] Latencia objetivo: < 1.5s entre que el usuario termina de hablar y el agente empieza

**Entregable:** mantener una conversación de 5 turnos sobre cualquier tema, con menos de 1.5s de latencia. La voz debe sonar natural.

**Métricas de aceptación:**
- Latencia P50 < 1.2s, P95 < 2s
- La voz no suena robótica ni entrecortada
- El agente no interrumpe al usuario

---

### Fase 2 — RAG: base de conocimiento de la clínica (Semana 3-4)

**Objetivo:** el agente conoce la clínica. Sabe qué especialidades hay, qué médicos, qué horarios, qué obras sociales acepta.

**Fuentes de ingesta (en orden de complejidad):**
1. Web crawl del sitio de la clínica con Firecrawl
2. PDFs (listado de médicos, aranceles, cobertura por obra social)
3. Datos estructurados via API (si la clínica tiene sistema de turnos: Docplanner, Medicloud, etc.)

**Autonomous RAG pattern:**
```
Pregunta del usuario
  → búsqueda en KB local (Qdrant)
  → ¿relevancia suficiente? → responde
  → ¿no suficiente? → búsqueda web (DuckDuckGo/Tavily) → responde con cautela
  → ¿sigue sin saber? → escala a humano
```

**Tareas:**
- [ ] Pipeline de ingesta: Firecrawl → LangChain → FastEmbed → Qdrant (colección `kb`)
- [ ] Retrieval con scoring de relevancia
- [ ] Prompt del agente actualizado: "Respondé solo con información que tenés. Si no sabés, decilo y ofrecé derivar."
- [ ] Fallback a web search cuando KB local no tiene la info
- [ ] Guardrails anti-alucinación: si el retrieved context no contiene la info, el agente dice "no tengo esa información" en vez de inventar

**Entregable:** el agente puede responder correctamente el 90%+ de las preguntas frecuentes de una clínica real.

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

| Métrica | Target |
|---------|--------|
| Latencia de respuesta P50 | < 1.2s |
| Latencia de respuesta P95 | < 2.0s |
| Tasa de resolución sin humano | > 80% |
| Tasa de alucinación / respuesta incorrecta | < 2% |
| NPS del paciente que usó el agente | > 7/10 |
| Costo por minuto de conversación | < USD 0.15 (para vender a USD 0.25-0.30) |

---

## Roadmap visual

```
Semana 1   │ Fase 0: Cimientos
Semana 2-3 │ Fase 1: Loop de voz (end-to-end sin RAG)
Semana 3-4 │ Fase 2: RAG + KB de la clínica
Semana 4-5 │ Fase 3: Flows de clínica (turnos, cobertura, info)
Semana 5-6 │ Fase 4: Memoria entre sesiones (Mem0)
Semana 6   │ Fase 5: Handoff a humano
Semana 7-8 │ Fase 6: Vertical Adapter (inmobiliaria como prueba)
Semana 8-10│ Fase 7: Dashboard + facturación
           │
           ▼ Beta con cliente real de clínica → primer ingreso
```

---

## Lo que NO hacemos en el MVP

- Fine-tuning de LLM o TTS (Unsloth está reservado para escala, post-validación)
- WhatsApp y web widget (el canal de voz por teléfono es suficiente para validar)
- Integración con sistemas de historia clínica (HIS/EMR)
- Cierre de ventas complejas
- Soporte multilingüe
- Modelo de IA propio (usamos APIs)

---

## Referencias técnicas (awesome-llm-apps)

| Patrón | Proyecto de referencia | Aplicación en nuestro stack |
|--------|----------------------|----------------------------|
| RAG sobre KB de cliente con Qdrant + Firecrawl | `customer_support_voice_agent` | Fase 2: ingesta de KB de la clínica |
| Doble-agente para optimizar respuesta para TTS | `voice_rag_openaisdk` | Fase 1: pipeline de respuesta |
| Memoria persistente con Mem0 + Qdrant | `llm_app_personalized_memory` | Fase 4: reconocimiento de pacientes |
| RAG con fallback a web search | `autonomous_rag` | Fase 2: cuando KB local no tiene la info |
| Orquestación multi-agente con OpenAI Agents SDK | `ai_audio_tour_agent` | Fase 3: agentes especializados por flow |
| Corrective RAG (CRAG) | `corrective_rag` | Post-MVP: reducir errores en respuestas críticas |
| RAG-as-a-service (Ragie.ai) | `rag-as-a-service` | Post-MVP: si queremos reducir infra propia |

---

## Próximo paso inmediato

Arrancar la Fase 0: crear la estructura del repositorio y tener el entorno funcionando.
La primera llamada al número de Twilio tiene que funcionar con voz de ElevenLabs antes de tocar ninguna otra cosa.
