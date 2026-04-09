# dashboard/api/

Backend del dashboard. Expone los datos de llamadas al frontend del cliente.

**Por qué existe:** Los datos del CallTrace (métricas, transcripciones, costos) necesitan un punto de acceso estructurado. FastAPI es el choice natural dado que el resto del stack es Python.

**Estado:** Fase 7 — no arrancar hasta tener el pipeline de voz validado.
