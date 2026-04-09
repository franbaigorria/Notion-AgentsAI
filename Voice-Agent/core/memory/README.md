# core/memory/

Capa de memoria entre sesiones. Recuerda información del usuario entre llamadas.

**Por qué existe:** El diferenciador de experiencia es que el agente recuerde al paciente. "La última vez que llamaste pediste turno con el Dr. García" no es posible sin memoria persistente. Se usa Mem0 con Qdrant como backend — el mismo servicio que ya se usa para RAG, minimizando la infraestructura.

## Implementación

Mem0 + Qdrant (colección `memory`, separada de la colección `kb` del RAG).
Identificación del usuario: número de teléfono entregado por Twilio al inicio de la llamada.

```python
class MemoryProvider:
    async def get(self, user_id: str) -> list[Memory]       # al inicio de llamada
    async def save(self, user_id: str, transcript: str)     # al cierre de llamada
```

## Qué se recuerda por usuario

- Nombre (si se presentó)
- Obra social y plan
- Médico preferido o de cabecera
- Última especialidad consultada
- Si tiene turno próximo

## Requerimientos

- **RQ-02** — la memoria es por usuario y por vertical; no se mezcla entre negocios
- **RQ-03** — reporta latencia de get/save
