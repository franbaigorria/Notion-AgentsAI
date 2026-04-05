# core/

El motor del agente de voz. Contiene todo el código que es idéntico sin importar el negocio o los proveedores.

**Por qué existe:** El core nunca cambia cuando se agrega un vertical nuevo ni cuando se cambia de proveedor. Es la separación fundamental entre "la plataforma" y "la configuración". Todo lo que esté acá debe funcionar igual para una clínica que para una inmobiliaria.

**Principio:** Si una pieza de lógica depende del nombre del negocio, de una API específica, o de un proveedor concreto — no pertenece acá.

## Subcarpetas

| Carpeta | Responsabilidad |
|---------|----------------|
| `stt/` | Conversión de audio a texto |
| `tts/` | Conversión de texto a audio |
| `llm/` | Generación de respuestas |
| `rag/` | Recuperación de información de la base de conocimiento |
| `memory/` | Memoria entre sesiones por usuario |
| `orchestrator/` | Coordina el pipeline completo por llamada |
| `escalation/` | Detección y handoff a humano |
| `telephony/` | Entrada/salida de audio (Twilio + modo local) |

## Requerimientos que cubre

- **RQ-01** — cada subcarpeta expone una interfaz base; las implementaciones concretas son intercambiables
- **RQ-03** — el orchestrator registra métricas de latencia y resultado por cada capa
- **RQ-04** — el orchestrator acumula costos por proveedor durante la llamada
- **RQ-06** — cada adapter soporta lista de proveedores con fallback automático
