# adapters/calendar/

Integración con sistemas de agenda. Permite al agente verificar disponibilidad, reservar, y cancelar turnos.

**Por qué existe:** La acción más crítica del vertical clínica es sacar un turno. El sistema de agenda varía por cliente: algunos usan Docplanner, otros Google Calendar, otros sistemas propios. Este adapter aísla esa variabilidad.

## Implementaciones planificadas

| Archivo | Sistema | Estado |
|---------|---------|--------|
| `google_calendar.py` | Google Calendar API | MVP (fallback universal) |
| `docplanner.py` | Docplanner API | MVP (sistema más común en AR) |

## Contrato de la interfaz

```python
class CalendarAdapter:
    async def get_availability(self, specialty: str, date_range: DateRange) -> list[Slot]
    async def book(self, slot: Slot, patient: Patient) -> Booking
    async def cancel(self, booking_id: str) -> bool
```
