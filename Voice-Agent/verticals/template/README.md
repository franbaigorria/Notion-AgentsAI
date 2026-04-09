# verticals/template/

Plantilla vacía para crear un nuevo vertical de negocio.

**Por qué existe:** Documentar el contrato que debe cumplir cualquier nuevo vertical. Copiar esta carpeta y completar los 6 archivos es todo lo que se necesita para lanzar un nuevo negocio en el sistema.

## Cómo usar esta plantilla

```bash
cp -r verticals/template verticals/nuevo_negocio
# Completar los 6 archivos
# Ejecutar ingesta de KB
# Testear con llamadas locales (RQ-05)
# Deploy
```

## Archivos a completar

| Archivo | Qué va acá |
|---------|-----------|
| `config.yaml` | Nombre del agente, voice_id, language, timezone, llm_model, stt_language |
| `persona.md` | Descripción de la personalidad, tono, vocabulario, límites de lo que puede y no puede hacer |
| `flows.yaml` | Lista de conversation flows: nombre, pasos, condiciones de éxito y salida |
| `kb_sources.yaml` | URLs a crawlear con Firecrawl, rutas a PDFs, endpoints de APIs a consultar |
| `integrations.yaml` | Conectores a activar: calendar, crm, notifications (ver `adapters/`) |
| `escalation_rules.yaml` | Triggers de escalación, número/email de contacto del staff, tiempos de espera |

## Tiempo estimado

Un vertical con KB simple (sitio web + 1-2 PDFs) puede estar operativo en 1 día.
