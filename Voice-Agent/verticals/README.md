# verticals/

Configuración por vertical de negocio. Todo lo que cambia entre una clínica y una inmobiliaria vive acá.

**Por qué existe:** El core del agente es idéntico para cualquier negocio. Lo único que cambia es quién es el agente, cómo habla, qué sabe, qué puede hacer, y cuándo escala. Eso es configuración, no código. Agregar un nuevo vertical es copiar `template/` y completar 6 archivos YAML/Markdown.

## Estructura de un vertical

```
verticals/{nombre}/
  config.yaml            # nombre del agente, voz de ElevenLabs, idioma, timezone
  persona.md             # cómo habla, qué puede y no puede hacer, tono
  flows.yaml             # lista de conversation flows y sus pasos
  kb_sources.yaml        # de dónde viene la KB (URLs, PDFs, APIs)
  integrations.yaml      # qué conectores activa (calendar, CRM, etc.)
  escalation_rules.yaml  # cuándo escala y a quién
```

## Verticals

| Carpeta | Estado | Descripción |
|---------|--------|-------------|
| `clinica/` | activo (MVP) | Recepción médica: turnos, cobertura, info |
| `template/` | referencia | Plantilla vacía para nuevos verticals |

## Requerimientos

- **RQ-02** — el core lee la config del vertical al inicio; nunca tiene lógica hardcodeada de negocio
