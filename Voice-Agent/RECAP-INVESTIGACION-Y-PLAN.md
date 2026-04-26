# Recap Investigación y Plan — Voice Agent

**Fecha:** 26 de abril de 2026
**Para:** Reunión Pachu + Fran
**Propósito:** Sintetizar la investigación y conversaciones del día sobre cómo avanzar con el proyecto, decidir foco, y bajar a un plan ejecutable. El roadmap detallado de 4 semanas se comparte aparte.

---

## 1. Estado actual del proyecto (la foto honesta)

El proyecto es una plataforma de agentes de voz construida sobre LiveKit, pensada como multi-vertical. Hoy hay un solo vertical activo (clínica) y la arquitectura ya está pensada para sumar más con bajo esfuerzo de código.

**Lo que funciona:** El pipeline de voz STT → LLM → TTS está completo, deployado en Railway, andando con el stack Deepgram Nova-3 + Claude Haiku 4.5 + ElevenLabs Flash v2.5. El modo `pipeline` es el principal; existe también un modo `realtime` con OpenAI speech-to-speech como experimento.

**Lo que está construido pero dormido:** Toda la capa multi-tenant (PostgresTenantRegistry, FernetPostgresVault, migraciones Alembic, scripts de seed, tests de integración). Bien armada pero apagada con `USE_TENANT_REGISTRY=false` para simplificar el MVP.

**Lo que está como interface vacía o a medio hacer:**
- `core/knowledge/` — abstract sin implementación. No hay RAG real.
- `core/memory/` — abstract sin implementación. No hay memoria entre llamadas.
- `verticals/clinica/kb_sources.yaml` — slots definidos pero sin URLs/paths reales.
- `core/escalation/`, `core/capabilities/`, `adapters/calendar/`, `adapters/crm/` — directorios vacíos o stubs.
- Sin tests end-to-end del pipeline real.
- **Nunca probamos el agente con una llamada de teléfono real.** Solo via LiveKit room dispatch.

**Conclusión de estado:** La arquitectura está bien pensada y la base técnica funciona, pero hoy es un "copiloto conversacional sin contexto, sin memoria, sin acciones". Le falta lo que lo convierte en producto vendible.

---

## 2. El debate del día: vertical único vs agente general

Discutimos si conviene construir un agente que entienda muchos verticales o uno que se especialice.

**Conclusión: es un falso dilema. La respuesta correcta es:**
- **Arquitectura general** (la que ya tenemos: core agnostic + verticals como folders + config). No hay que cambiar nada del diseño.
- **Un solo vertical activo y bien resuelto al MVP** (clínica).
- **Segundo vertical** recién cuando el primero esté validado en un cliente real.

**Por qué no "agente general que sabe de todo":**
- Termina mediocre en todo. La persona, vocabulario y flujos cambian mucho entre rubros.
- El demo es débil: no podés mostrarle a una clínica una llamada de restaurante.
- La venta B2B es por casos concretos, no por plataforma genérica.

**Por qué no "vertical único hardcodeado":**
- Mata la replicabilidad. La arquitectura ya está lista para ser agnostic, sería un retroceso.

**Decisión recomendada:** funcionar como agencia con vertical clínica, replicar a otros verticales después de validar el primero. Cuando el patrón esté validado, sumar un nuevo rubro es básicamente copiar la carpeta `verticals/`.

---

## 3. Arquitectura de capas: qué cambia entre qué

Hoy todo está mezclado en `verticals/clinica/config.yaml`. Hay que separar tres capas conceptuales:

**Core (no cambia nunca):**
Plomería: cómo se conecta LiveKit, cómo se pluggea STT/LLM/TTS, cómo se levanta el worker. Ya está bien resuelto.

**Vertical (cambia entre rubros, no entre clientes del mismo rubro):**
Persona base, vocabulario del dominio, flujos típicos, reglas de escalación tipo, schema de KB. Vive en `verticals/clinica/`, `verticals/inmobiliaria/`, etc.

**Tenant (cambia entre clientes del mismo vertical):**
Info concreta del cliente: nombre, dirección, horarios, médicos, obras sociales aceptadas, voz elegida, número de transferencia, credenciales del calendar. **Hoy no existe como concepto separado.** Propuesta: crear `tenants/<cliente>/` con su yaml + secretos.

**Diferencia concreta entre clínica San Martín y otra clínica:** todo es data (nombre, equipo médico, obras sociales aceptadas, calendar credentials, voz, tono). Sin código.

**Diferencia entre clínica e inmobiliaria:** persona completa, vocabulario, flujos típicos, tools que el LLM puede llamar (Calendar vs CRM inmobiliario tipo Tokko), reglas de éxito (turno agendado vs lead calificado), pricing del servicio (por minuto vs por lead).

**Decisión técnica relacionada:** ¿usamos la capa Postgres+vault que Fran construyó? **Recomendación: no para MVP.** Mientras sean 1-5 clientes, YAML por carpeta es más simple, versionable en git, editable con cualquier editor. La capa Postgres se prende cuando haya onboarding self-service o secrets críticos que requieran audit/rotación.

---

## 4. Stack técnico definitivo para Argentina

Decidido capa por capa, con justificación y costo por minuto.

| Capa | Provider | Justificación |
|---|---|---|
| Telefonía | Twilio (MVP) → Telnyx/local (escala) | Twilio rápido para arrancar; caro pero estándar. Telnyx más barato para LATAM. Providers locales para Argentina cuando escalemos. |
| STT | Deepgram Nova-3 | Rápido, streaming, español multidialecto bueno. |
| LLM | Claude Haiku 4.5 | Velocidad + calidad de español + tool use nativo. Si la latencia molesta: evaluar Groq con Llama. |
| TTS | ElevenLabs Flash v2.5 | Mejor calidad disponible, voz custom. Si costo aprieta: Cartesia. |
| Hosting worker | Railway US-East | Lo mantenemos. Fly.io São Paulo queda como experimento opcional para mes 2 si la latencia molesta. |
| LiveKit | LiveKit Cloud | Simple, barato, ya integrado. |
| Persistencia | SQLite local (MVP) → Supabase (multi-cliente) | Empezamos simple. Postgres gestionado cuando sumemos segundo cliente. |

**Costos por minuto de llamada estimados:**

| Item | USD/min |
|---|---|
| Telefonía Twilio AR | 0.015–0.025 |
| LiveKit Cloud | 0.005 |
| Deepgram STT | 0.0043 |
| Claude Haiku | 0.001–0.003 |
| ElevenLabs TTS | 0.04–0.08 |
| **Total** | **~0.07–0.12 USD/min** |

**Modelo de negocio implícito:** Si una clínica recibe 50 llamadas/día de 4 min promedio = 200 min/día = ~6000 min/mes = USD 420–720/mes en costos puros. **Pricing piso para que cierre el modelo: USD 1500–2500/mes al cliente.** Comparado con sueldo de recepcionista (USD 600–900/mes), no se vende como reemplazo sino como **aumento de capacidad** — la recepcionista atiende lo importante, el agente liquida las repetitivas.

---

## 5. Bloqueo crítico hoy: la llamada telefónica real

**Nunca probamos el agente con una llamada de teléfono real.** Solo via dispatch en LiveKit room. Esto es el bloqueante #1 antes de avanzar con cualquier feature nueva.

**Por qué es crítico:**
- Sin esto no medimos latencia real (los tests vía LiveKit room son optimistas)
- No detectamos problemas de barge-in, codecs SIP, ruido, calidad de audio reales
- No podemos hacer demo a nadie
- No grabamos video de demo

**Cómo destrabarlo:** Twilio + número virtual + SIP trunk → LiveKit Cloud → agente. LiveKit tiene guía oficial paso a paso. Es 1 día bien encarado.

**Esto va primero en el plan.**

---

## 6. Qué necesita el cliente (clínica)

**Cero hardware. Cero software. Cero conocimientos técnicos.** Esto es argumento de venta principal.

Lo único que la clínica necesita hacer:
1. Activar desvío de llamadas hacia el número que le damos (o publicar el nuevo número como canal adicional).
2. Compartir su Google Calendar con un email/service account que le damos. Si no tiene, le armamos en 5 min.
3. Darnos info para llenar la KB: horarios, médicos, obras sociales, aranceles, FAQs, políticas, número de transferencia humana.
4. Confirmar quién atiende las escalaciones (recepcionista en horario, celular del dueño fuera de horario).
5. Estar disponible las primeras dos semanas para feedback.

**NO necesita:** instalar software, comprar hardware, cambiar su sistema actual de turnos, ni saber nada técnico.

---

## 7. Qué necesitamos nosotros

**Cuentas técnicas (todas con billing prendido):**
LiveKit Cloud, Twilio, Deepgram, Anthropic, ElevenLabs, Railway, Google Cloud (Service Account), GitHub.

**Cuentas comerciales:**
Dominio + email profesional, LinkedIn, Notion/Drive, Calendly, Stripe + MercadoPago (cuando cobremos), AFIP/monotributo o SRL.

**Costos fijos mensuales sin clientes:**
~USD 50–170/mes (Railway + LiveKit base + Twilio número + dominio + APIs de testing).

**Equipamiento:**
- Sus computadoras actuales (16GB+ RAM)
- Dos celulares para testear cliente + escalación a humano
- Auriculares de buena fidelidad para detectar artefactos de TTS o latencia
- Idealmente segundo número argentino para tests realistas

---

## 8. Flujo end-to-end de una llamada (para tener la foto entera)

1. Paciente llama al número publicado por la clínica
2. Twilio recibe y enruta vía SIP trunk a LiveKit Cloud
3. LiveKit crea room y dispara dispatch al worker
4. Railway: el worker (agente Python) se conecta a la room
5. Carga config del tenant, construye persona + KB
6. Saluda con la voz configurada
7. Conversación en streaming: audio → Deepgram STT → Claude LLM → ElevenLabs TTS → audio. Cada turno ~500-1000ms.
8. Si Claude usa tool: llama Google Calendar API o transfer SIP a humano
9. Cierre: se guarda transcript + summary en SQLite/Postgres
10. Métricas se actualizan

Cada eslabón tiene costo y latencia. Y cada uno puede caerse — por eso reliability importa.

---

## 9. Proceso de onboarding por cliente (operativa)

Para cada cliente nuevo (~6-10 horas iniciales):

1. Contrato firmado (aunque sea piloto). Define alcance, duración, datos, derecho a usar como caso de éxito.
2. Reunión de discovery (1 hora) para levantar la KB con dueño/recepcionista.
3. Setup técnico interno (2-4 horas):
   - Crear `tenants/<cliente>/`
   - Llenar KB
   - Provisionar número Twilio
   - Configurar Service Account de Google Calendar
   - Setup número de transferencia humana
   - Deploy a Railway
4. QA interna: 10-15 llamadas de prueba.
5. Soft launch con monitoreo en vivo.
6. Primera semana de hypercare con revisión diaria + reunión de feedback al cierre.
7. Estado régimen: revisión semanal x 4 semanas, después mensual.

A 5+ clientes el onboarding manual no escala — vamos a necesitar UI de admin (mes 2-3, no MVP).

---

## 10. Riesgos y trabas conocidas

1. **No tenemos cliente real todavía** — riesgo #1, todo lo demás es secundario. Estamos optimizando para una clínica imaginaria. Mitigación: definir bien una "clínica modelo" ficticia para demos consistentes.
2. **Telefonía argentina** — Twilio/Telnyx lleva tiempo de setup, los números argentinos son más caros y burocráticos. Plan B: empezar con número US virtual para pruebas tech, después argentino para piloto.
3. **Latencia desde Argentina** — Railway US-East + APIs en USA puede sumar latencia perceptible. Plan B: medir, si molesta evaluar Fly.io São Paulo en mes 2.
4. **Costo por llamada vs disposición a pagar** — Si la clínica solo paga USD 800/mes, no cierra. Hay que validar pricing con clientes reales.
5. **Integración con sistemas existentes** — Si la clínica usa DocPlanner/MediTurnos y exige integración, es desarrollo caso a caso. Plan B: empezar con Google Calendar paralelo, recepcionista migra.
6. **Manejo de interrupciones, ruido, barge-in** — Las llamadas reales son más caóticas que los tests. Plan: probar con teléfono real cuanto antes.
7. **Escalación a humano** — SIP transfer en Twilio requiere setup. Plan B: conferencia three-way o "te paso un número directo".
8. **Fallbacks cuando algo se cae** — ElevenLabs/Claude/Calendar caídos. Plan: reliability layer en semana 3.
9. **Compliance con datos médicos** — Grabaciones, consentimiento, retención. Plan: implementar mínimo viable en semana 4.
10. **Soporte/oncall** — ¿Quién atiende a las 11pm un sábado? Definir desde ahora roles o aceptar "best effort" y comunicarlo al cliente.
11. **Identidad legal/fiscal** — Cuando aparezca el primer cobro va a apretar. Mejor pensarlo ya: monotributo, SRL, factura personal.

---

## 11. Roadmap simplificado (4 semanas → MVP probado)

**Semana 1 — Destrabar llamada real + arquitectura tenant**
- Twilio + número + SIP trunk → LiveKit funcionando
- Primera llamada real desde celular, latencia medida
- Refactor: separar `tenants/san-martin/` de `verticals/clinica/`
- Runbooks de telefonía y onboarding

**Semana 2 — KB + memoria + persona**
- KB estática completa para clínica San Martín ficticia
- Inyección en system prompt
- Memoria mínima entre llamadas (SQLite)
- Persona afinada con 20-30 llamadas de prueba

**Semana 3 — Tools + escalación + reliability**
- Adapter real Google Calendar como tool de Claude
- SIP transfer a humano funcionando
- Fallbacks cuando servicios fallan
- Test de carga manual

**Semana 4 — Métricas + polishing + piloto**
- Dashboard de métricas
- Compliance básico (consentimiento, grabación, retención)
- Voz/persona pulidas
- Video demo de 2 min
- Buscar primer cliente piloto

**Definición de éxito al cierre del mes:** Llamás a un número de teléfono argentino, atiende el agente con persona pulida, responde con info real de una clínica, agenda turno en Google Calendar, escala a humano cuando hace falta, todo estable. Idealmente con cliente piloto comprometido.

---

## 12. Lo que NO entra en este mes (consciente)

- Multi-tenant real con Postgres y vault → dormido hasta tener 2+ clientes pagando
- Segundo vertical (vet, inmobiliaria, etc) → después
- RAG vectorial con Qdrant → KB estática alcanza para clínica
- Modo realtime de OpenAI → pipeline está más maduro y debugueable
- Migración de hosting → Railway queda
- UI de admin para gestionar tenants → mes 2-3
- Onboarding self-service → producto distinto

---

## 13. Decisiones para tomar juntos en esta reunión

1. ¿Confirmamos el foco en **clínica como único vertical para el mes**, sin distraernos con otros rubros?
2. ¿Aprobamos la separación `verticals/` vs `tenants/` para arrancar?
3. ¿Confirmamos el **stack técnico recomendado** o queremos discutir alguna capa?
4. ¿Quién toma cada bloque de las 4 semanas? Telefonía es lo más fricción inicial, KB es lo más creativo, Calendar es lo más técnico.
5. ¿Modelo de pricing para el piloto: gratis 1-2 meses + caso de éxito, o ya cobrar simbólico?
6. ¿Identidad legal/fiscal del proyecto: facturamos personal, monotributo, SRL?
7. ¿Cuándo activamos las cuentas que faltan con billing (Twilio sobre todo)?
8. ¿Cómo dividimos soporte/oncall cuando haya cliente activo?
9. ¿Compramos los dos celulares de prueba y el segundo número ya, o esperamos?
10. ¿Cuál es la "clínica modelo" ficticia para demo? Inventamos juntos los datos plausibles.

---

## 14. Próximo paso inmediato (post-reunión)

Si todo se confirma: arrancar **mañana mismo** con el setup de Twilio + SIP trunk a LiveKit. Es el bloqueante #1 y lo demás depende de tener el teléfono andando.
