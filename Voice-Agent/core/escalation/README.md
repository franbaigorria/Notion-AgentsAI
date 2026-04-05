# core/escalation/

Detecta cuándo el agente no puede resolver la situación y ejecuta el handoff a un humano.

**Por qué existe:** El agente nunca puede dejar a un usuario tirado. Cuando no sabe, cuando el tema está fuera de scope, o cuando el usuario lo pide — hay que pasar a un humano de forma elegante. Las reglas de cuándo escalar y a quién son configurables por vertical.

## Triggers de escalación

Detectados por el orchestrator durante el loop de conversación:

- El usuario pide explícitamente hablar con una persona
- El RAG no encontró resultado en KB ni en web (source: none)
- El agente no pudo resolver en N intentos (configurable por vertical)
- El tema detectado está fuera del scope definido en el vertical

## Flujo de handoff

```
Trigger detectado
  → Agente avisa: "Voy a pasarte con alguien del equipo, un momento."
  → Genera resumen de la conversación
  → Notifica al staff (WhatsApp/email con resumen)
  → Twilio transfiere la llamada
  → Si no atiende en N segundos: buzón de voz + SMS de callback
```

## Requerimientos

- **RQ-02** — las reglas de escalación (`escalation_rules.yaml`) son configurables por vertical
- **RQ-03** — el CallTrace registra `resolution: escalated` y el trigger que lo causó
