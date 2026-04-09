# adapters/

Conectores a sistemas externos. Cada adapter encapsula la integración con un servicio de terceros.

**Por qué existe:** El agente necesita interactuar con sistemas del cliente (calendarios, CRMs, WhatsApp) pero esos sistemas varían por cliente y vertical. Los adapters aíslan esa variabilidad: el orchestrator llama a una interfaz genérica (`CalendarAdapter.book()`), sin saber si por detrás está Google Calendar o Docplanner.

## Subcarpetas

| Carpeta | Qué hace |
|---------|---------|
| `calendar/` | Reserva, consulta y cancela turnos en sistemas de agenda |
| `crm/` | Lee y escribe datos de clientes/pacientes en CRMs |
| `notifications/` | Envía notificaciones al staff y confirmaciones al usuario |
| `kb_ingestion/` | Ingesta fuentes de datos en la base de conocimiento (Qdrant) |

## Requerimientos

- **RQ-02** — cada vertical declara qué adapters usa en `integrations.yaml`; el core los instancia sin saber los detalles
- **RQ-01** — cada tipo de adapter tiene una interfaz base; las implementaciones concretas son intercambiables
