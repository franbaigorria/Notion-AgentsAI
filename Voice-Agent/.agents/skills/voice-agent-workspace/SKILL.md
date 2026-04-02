---
name: voice-agent-workspace
description: Protocolo de workspace para el proyecto Agente de Voz Argentino. Define DÓNDE y CÓMO guardar información en Notion mientras el equipo trabaja. Usar esta skill siempre que se necesite registrar una tarea, aprendizaje, herramienta evaluada, decisión de arquitectura o gasto dentro del proyecto del agente de voz. Se activa automáticamente cuando: se toma una decisión técnica, se evalúa o elige una tool, se acuerda una tarea, se completa un experimento, se agrega una suscripción, o se hace cualquier discovery no trivial durante el trabajo en el agente de voz. Si hay duda sobre si guardar algo — guardarlo.
---

# Voice Agent Workspace Protocol

Protocolo de memoria persistente para el proyecto Agente de Voz Argentino — dos founders construyendo un voice agent con acento argentino, RAG, para pymes latinoamericanas. Este archivo define exactamente dónde vive cada tipo de información en Notion y cuándo guardarla.

**Regla #1**: Guardar de forma PROACTIVA. No esperar a que el usuario lo pida. Si algo fue decidido, descubierto, acordado o pagado — guardarlo ahora.

**Regla #2**: Leer `workspace/notion-context.md` ANTES de cualquier operación en Notion. Ahí están los IDs reales de las databases.

---

## Tabla de Triggers — Cuándo Guardar

| Situación | Database destino | Acción |
|---|---|---|
| Tarea acordada o identificada | **Tareas** | Crear fila nueva |
| Discovery técnico (latencia, patrón RAG, bug, gotcha) | **Aprendizajes** | Crear fila nueva |
| Insight de mercado o de usuario | **Aprendizajes** | Crear fila nueva |
| Tool evaluada, elegida o descartada | **Stack & Herramientas** | Crear o actualizar fila |
| Suscripción nueva, API, infra — cualquier costo | **Inversión / Gastos** | Crear fila nueva |
| Decisión técnica relevante (arquitectura, stack, patrón) | **Decisiones de Arquitectura** (página) | Agregar bloque |
| Experimento completado | **Tareas** (marcar hecho) + **Aprendizajes** (resultado) | Dos entradas |
| Tarea bloqueada | **Tareas** | Actualizar estado a Bloqueado + nota del bloqueo |

**Si hay duda entre Aprendizajes y Decisiones de Arquitectura**: si es una decisión tomada con alternativas descartadas → Decisiones. Si es algo descubierto sin haber evaluado opciones → Aprendizajes.

---

## Schemas de cada Database

### Tareas

```
Name:         título de la tarea (obligatorio, imperativo: "Prototipar voice_rag_openaisdk")
Status:       Por hacer | En curso | Bloqueado | Hecho
Área:         Producto | Técnico | Negocio
Responsable:  Francisco | Compañero | Ambos
Prioridad:    Alta | Media | Baja
Notas:        contexto, links o condiciones de bloqueo (opcional)
```

### Aprendizajes

```
Título:   resumen en 1 línea — qué se aprendió (obligatorio)
Fecha:    fecha del discovery (hoy si no se especifica)
Área:     Técnico | Mercado | Usuario | Negocio
Impacto:  Alto | Medio | Bajo
Fuente:   experimento | conversación | lectura | test | otro
Detalle:  desarrollo completo — qué pasó, por qué importa, cómo aplica al proyecto
```

El campo **Detalle** es el más importante. No guardar solo el título — el valor está en el contexto.

### Stack & Herramientas

```
Nombre:                nombre de la herramienta (obligatorio)
Para qué:              caso de uso específico dentro del agente de voz
Costo/mes:             número en USD (0 si es free tier o open source)
Alternativas evaluadas: otras opciones que se consideraron
Estado:                En uso | Descartada | A evaluar
Decisión:              por qué se eligió o descartó — razonamiento, no solo la conclusión
```

### Inversión / Gastos

```
Nombre:             nombre del servicio o suscripción (obligatorio)
Costo/mes:          número en USD
Desde cuándo:       fecha de inicio del gasto
Quién paga:         Francisco | Compañero | Empresa
Necesaria para MVP: Sí | No | Tal vez
Notas:              plan contratado, límites de uso, condiciones relevantes
```

### Decisiones de Arquitectura (página, no database)

Cada decisión se agrega como un bloque con este formato:

```markdown
## [YYYY-MM-DD] — [Decisión tomada en 1 línea]

**Por qué**: motivación — qué problema resuelve o qué restricción impone
**Alternativas descartadas**: qué se evaluó y por qué no se eligió
**Consecuencias**: impacto esperado en el proyecto (técnico, operativo, económico)
```

---

## Procedimiento Estándar de Guardado

1. Identificar el tipo de información → match con la tabla de triggers
2. Leer `workspace/notion-context.md` → obtener el ID de la database correcta
3. Mapear la información a los campos del schema
4. Crear la fila o bloque en Notion
5. Confirmar con título y URL de lo creado

Si la información encaja en más de una database (ej: experimento completado), crear ambas entradas. No elegir una sola.

---

## Manejo de Incertidumbre

| Situación | Qué hacer |
|---|---|
| La database no existe todavía | Avisar al usuario, ofrecer crearla con el schema definido arriba, luego actualizar `notion-context.md` con el ID real |
| Un campo no existe en la DB | Usar el campo más cercano disponible y mencionarlo al usuario |
| Ambigüedad sobre qué database usar | Elegir la más probable, decirlo explícitamente antes de guardar |
| Falta un campo obligatorio | Usar "TBD" en ese campo y completar el resto — no bloquear el guardado |
| El ID en notion-context.md dice "TBD" | Correr el Setup Inicial antes de continuar |

---

## Setup Inicial (solo la primera vez)

Si `workspace/notion-context.md` muestra IDs como `TBD`, las databases no fueron creadas todavía.

**Pasos:**

1. Crear las 4 databases dentro del teamspace **Agent AI** en Notion
2. Aplicar los schemas definidos arriba como properties de cada database
3. Crear la página **Decisiones de Arquitectura** dentro del mismo teamspace
4. Actualizar `workspace/notion-context.md` con los IDs y URLs reales de cada database y página
5. Asegurarse de que la integración `claude` tenga acceso a las databases nuevas (en cada database: `···` → Add connections → claude)

El setup solo se hace una vez. Después, todos los guardados van directo a los IDs resueltos.

---

## Contexto del Proyecto

Para entender qué guardar y cómo priorizarlo:

- **Producto**: voice agent con acento argentino, RAG sobre datos de negocio propios del cliente
- **Target**: pymes en Argentina/LatAm con alto volumen de consultas repetitivas
- **Canal principal a validar**: voz (también WhatsApp)
- **Stack MVP**: OpenAI o Anthropic (LLM) + ElevenLabs (TTS) + Qdrant (vector DB) + FastEmbed (embeddings)
- **Diferenciador**: naturalidad local, baja latencia, comportamiento seguro ante incertidumbre
- **Riesgos clave**: latencia en voz en tiempo real, costo por conversación antes de validar conversión, confianza del usuario en agente artificial
- **Primer experimento a hacer**: prototipar `voice_rag_openaisdk` con documentos reales de una pyme

Cuando registres un aprendizaje o una decisión, conectarlo siempre con cómo afecta a estos ejes: latencia, costo, naturalidad, precisión, escalabilidad.
