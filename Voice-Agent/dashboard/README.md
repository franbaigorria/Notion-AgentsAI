# dashboard/

Panel de control para el cliente. Muestra métricas de llamadas y permite gestionar la configuración del vertical.

**Por qué existe:** El cliente necesita saber qué está pasando: cuántas llamadas se resolvieron, cuántas escalaron, cuántos minutos se consumieron, cuánto debe pagar. Y nosotros necesitamos poder emitir la factura. Esta carpeta es la Fase 7 del MVP.

**Estado:** Postergado. No se toca hasta que el pipeline de voz esté validado en producción.

## Subcarpetas

| Carpeta | Responsabilidad |
|---------|----------------|
| `api/` | FastAPI endpoints que exponen los logs de llamadas y métricas |
| `frontend/` | UI web del cliente (tech a definir en Fase 7) |

## Métricas que expone (MVP)

- Log de llamadas: fecha, duración, número, resolución
- Transcripción completa por llamada
- Tasa de resolución vs. escalación
- Minutos consumidos en el período
- Costo estimado del período
