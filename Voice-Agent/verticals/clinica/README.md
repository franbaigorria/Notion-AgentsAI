# verticals/clinica/

Primer vertical del MVP. Reemplaza la recepción de clínicas y consultorios privados en Argentina.

**Por qué es el primero:** Buenos Aires procesa ~40.000 turnos médicos por día. Una recepcionista full-time cuesta ~USD 400-500/mes. El agente atiende 24/7 con disponibilidad inmediata. El ROI es claro para el cliente y la conversación es suficientemente compleja para probar todas las capacidades del sistema.

## Flows de conversación

1. **Agendar turno** — detecta especialidad → verifica disponibilidad → agenda → confirma por SMS
2. **Consulta de cobertura** — detecta obra social + plan → busca en KB → responde o deriva
3. **Info general** — horarios, cómo llegar, teléfono directo, estacionamiento
4. **Reagendar / cancelar** — busca el turno existente → modifica → confirma

## Obras sociales prioritarias en la KB

OSDE, Swiss Medical, Galeno, IOMA, PAMI, Medicus, Jerárquicos

## Archivos de configuración

| Archivo | Contenido |
|---------|-----------|
| `config.yaml` | Nombre del agente, voice ID de ElevenLabs, idioma: es-AR |
| `persona.md` | Tono cálido y profesional, vocabulario médico básico |
| `flows.yaml` | Los 4 flows definidos arriba con sus pasos |
| `kb_sources.yaml` | URL del sitio de la clínica, PDFs de aranceles y coberturas |
| `integrations.yaml` | Google Calendar (fallback), Docplanner (si aplica) |
| `escalation_rules.yaml` | Escala si: pide humano, emergencia, tema fuera de scope |
