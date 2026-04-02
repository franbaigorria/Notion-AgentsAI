# Browser Use - Automatización Web con IA

## One-Line Pitch

SDK/API para automatización de navegadores con IA: describí una tarea en lenguaje natural, ejecuta en browsers stealth con CAPTCHA solving y proxies, devolvé datos estructurados.

## Problem

- Muchos procesos empresariales dependen de navegadores web sin APIs disponibles
- La automatización tradicional (Selenium, Puppeteer) es frágil y requiere programación
- Los trámites online en LatAm tienen CAPTCHAs, bloqueos y interfaces complejas
- Las empresas necesitan extraer datos de múltiples fuentes web en paralelo

## User And Buyer

- Primary user: pymes, freelancers, equipos de operaciones
- Economic buyer: empresas que automatizan procesos repetitivos o necesitan extracción de datos web
- Initial market or niche: empresas en LatAm con trámites gubernamentales frecuentes y e-commerce

## MVP

- Wrapper sobre Browser Use Cloud API con flujos pre-armados para casos comunes
- Interfaz simple: elegir flujo → configurar credenciales → ejecutar
- Output estructurado (JSON/CSV) listo para usar

### Explicitly Out Of Scope

- Desarrollo de flujos custom desde cero
- Soporte para sitios con autenticación MFA avanzada
- Reemplazo de herramientas de RPA empresarial completas

## AI Layer

- Core capabilities: browser automation con lenguaje natural, extracción de datos estructurados
- Context model: sesiones persistentes con cookies/login state
- Key quality constraints: baja tasa de fallo, stealth efectivo, costo predecible

## Product Notes

- La diferencia clave vs "research": Research lee internet como un humano que googlea. El agente usa internet como un humano que trabaja. Research nunca puede entrar a tu AFIP y descargar un archivo.
- Browser Use mantiene sesiones persistentes con cookies — eso requiere identidad, no solo lectura pública.
- Para prototipar: Open Source. Para producción: Cloud (resuelve infra, stealth, CAPTCHAs).

## Use Cases

### Near-Term

- Monitoreo de precios competencia (e-commerce)
- Extracción de datos de portales sin APIs
- Automatización de trámites gubernamentales repetitivos (AFIP, ANSES, etc.)

### Longer-Term

- Auditoría de presencia digital (listings, reseñas, SEO on-page)
- Onboarding automático de empleados en múltiples herramientas SaaS
- RPA conversacional: "sacá un reporte del dashboard" → ejecuta en browser

## Research

### Open Source vs Cloud

| Aspecto | Open Source | Cloud |
|---|---|---|
| Infraestructura | Self-hosted, browsers propios | Todo managed |
| Stealth/CAPTCHA | Manual, servicios adicionales | De fábrica |
| Costo | Más barato en volumen alto | Comparable a GPT-4o |
| Esfuerzo | Más ingeniería | Menos setup |
| Recomendación | Prototipar/Validar | Producción |

### Research vs Agente Browser

- **Research**: lector rápido de información pública, sin identidad, no puede interactuar con sistemas autenticados
- **Browser Agent**: mantiene sesiones con cookies, puede hacer clic, descargar, subir, loguearse
- **La línea**: en cuanto hay credenciales de por medio, ya es territorio de agente

## Risks

### Technical

- Sites con anti-bot avanzado pueden bloquear el agente
- Fluctuación de costos según complejidad de las tareas
- Calidad variable del output según la estructura del sitio target

### Business

- Mercado puede no pagar lo suficiente por automatización web
- Herramientas de RPA existentes (UiPath, Automation Anywhere) tienen más features
- Dependencia de la API de Browser Use como proveedor

## Moat Hypotheses

- Flujos pre-armados para mercados verticales específicos (LatAm, trámites locales)
- Mejor experiencia de usuario para no-técnicos
- Integración con sistemas locales del cliente

## Suggested Repo

- Repo name: TBD (pendiente de validación)
- Likely scope: Browser Use API wrapper, flujo templates, output formatters, scheduling

## Open Questions

- ¿Qué trámites o procesos son más frecuentes y dolorosos en el mercado target?
- ¿El volumen de uso justifica el costo de la API vs hacerlo manual?
- ¿Los usuarios prefieren flujos pre-armados o flexibilidad total?
- ¿Vale la diferencia el costo de Cloud vs Open Source para el volumen esperado?

## Next Step

- Identificar 2-3 flujos de automatización específicos para LatAm
- Validar que el agente funciona con esos flujos usando Browser Use Open Source
- Medir costo real por tarea y comparar con el valor que genera
