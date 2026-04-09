# adapters/notifications/

Envío de notificaciones al staff y confirmaciones al usuario.

**Por qué existe:** El agente necesita dos tipos de comunicación asíncrona: confirmar turnos al usuario (SMS) y notificar al staff cuando hay una escalación. Esas notificaciones usan canales distintos y van a destinatarios distintos.

## Implementaciones planificadas

| Archivo | Canal | Uso |
|---------|-------|-----|
| `sms.py` | Twilio SMS | Confirmación de turno al usuario |
| `whatsapp.py` | Twilio WhatsApp | Notificación de escalación al staff |
| `email.py` | SMTP / SendGrid | Alternativa de notificación al staff |

## Contrato de la interfaz

```python
class NotificationAdapter:
    async def send(self, to: str, message: str, channel: str) -> bool
```
