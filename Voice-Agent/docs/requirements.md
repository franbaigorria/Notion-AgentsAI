# Requerimientos de Arquitectura — Voice Agent Platform

Estos son los requerimientos que guían las decisiones de arquitectura del proyecto.
Toda decisión técnica debe justificarse contra al menos uno de estos requerimientos.

---

## RQ-01 — Intercambio de proveedor por capa

**Qué:** Cada capa del pipeline de voz (STT, LLM, TTS, telefonía) debe poder reemplazarse por otro proveedor sin modificar el resto del sistema.

**Por qué importa:** Los proveedores de IA evolucionan rápido. Quedar atado a un proveedor es un riesgo operativo y de costo.

**Implementación:** Adapter pattern — cada capa expone una interfaz base (`STTProvider`, `LLMProvider`, `TTSProvider`).

---

## RQ-02 — Vertical intercambiable (negocio configurable)

**Qué:** El mismo core del agente debe poder atender distintos rubros de negocio mediante configuración, sin tocar código.

**Por qué importa:** La capacidad de lanzar un nuevo vertical en días es el diferenciador del negocio.

**Implementación:** Cada vertical vive en `verticals/{nombre}/` con un `VerticalBundle` validado.

---

## RQ-03 — Acceso a Datos en 3 Capas Homogéneas

**Qué:** El agente NO accede a bases de datos o APIs directamente por vertical. Usa 3 interfaces unificadas:
1. **Knowledge Access:** Info estática (RAG, PDFs, Web).
2. **Memory Access:** Contexto e historial por usuario.
3. **Operational Access (Capabilities):** Herramientas transaccionales tipadas (Agenda, CRM).

**Por qué importa:** Mezclar la búsqueda de FAQs con la creación de un turno rompe la homogeneidad. La arquitectura debe permitir que una "Inmobiliaria" y una "Clínica" usen el mismo motor, pero le pasen distintas capabilities.

**Implementación:**
- `core/knowledge/base.py` -> `KnowledgeProvider`
- `core/memory/base.py` -> `MemoryProvider`
- `core/capabilities/base.py` -> `CapabilityProvider`

---

## RQ-04 — Observabilidad por paso
*(... Mantenemos las definiciones originales para métricas de latencia ...)*

## RQ-05 — Costo por conversación trazable
*(... Mantenemos las definiciones originales para costos ...)*

## RQ-06 — Modo de prueba sin telefonía real
*(... Mantenemos las definiciones originales ...)*

## RQ-07 — Degradación graceful por proveedor
*(... Mantenemos las definiciones originales ...)*
