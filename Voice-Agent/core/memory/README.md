# core/memory/

Capa de memoria persistente entre llamadas. Recuerda información del usuario a través de sesiones.

**Por qué existe:** El diferenciador de experiencia es que el agente recuerde al usuario. "La última vez que llamaste pediste turno con el Dr. García" no es posible sin memoria persistente. La capa usa Mem0 con Qdrant como backend — el mismo servicio que Knowledge, minimizando la infraestructura.

## Contrato de la interfaz

```python
class MemoryProvider(ABC):
    async def get(self, user_id: str, tenant_id: str) -> list[Memory]: ...
    async def save(self, user_id: str, tenant_id: str, transcript: str) -> None: ...

@dataclass
class Memory:
    key: str    # identificador de la memoria (ej: user_id)
    value: str  # contenido extraído del transcript
```

## Convención de namespace en Mem0/Qdrant

```
namespace = mem_{tenant_id}

Ejemplo:
  tenant "clinica_del_valle"  →  namespace "mem_clinica_del_valle"
  tenant "centro_medico_sur"  →  namespace "mem_centro_medico_sur"
```

## Aislamiento por tenant

Un mismo número de teléfono puede llamar a dos tenants distintos del mismo vertical. La memoria es **completamente separada** — un paciente que usa dos clínicas no tiene su historial mezclado.

```python
# El mismo user_id en dos tenants distintos → stores separados
await provider.get(user_id="+5491155443322", tenant_id="clinica_a")   # memoria de Clinica A
await provider.get(user_id="+5491155443322", tenant_id="clinica_b")   # memoria de Clinica B (independiente)
```

## Uso en el flujo de llamada

```python
# Al inicio de la llamada
memories = await memory_provider.get(user_id=phone_number, tenant_id=tenant_id)
# → inject memories como contexto del LLM

# Al cierre de la llamada
await memory_provider.save(user_id=phone_number, tenant_id=tenant_id, transcript=full_transcript)
```

## Qué se recuerda por usuario

- Nombre (si se presentó)
- Obra social y plan
- Médico preferido o de cabecera
- Última especialidad consultada
- Si tiene turno próximo

## Requerimientos

- **RQ-02** — la memoria es por `user_id` + `tenant_id`; no se mezcla entre tenants ni entre negocios
- **RQ-03** — reporta latencia de `get` y `save`
