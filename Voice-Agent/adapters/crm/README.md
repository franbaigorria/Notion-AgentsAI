# adapters/crm/

Integración con sistemas de gestión de clientes. Permite al agente leer y actualizar datos de pacientes o clientes.

**Por qué existe:** Algunos clientes tienen CRMs propios con datos de pacientes. En lugar de depender exclusivamente de la memoria de Mem0, este adapter permite leer datos existentes (historial de turnos, datos de contacto) al inicio de la llamada.

**Estado en el MVP:** Postergado a Fase 3+. La memoria de Mem0 es suficiente para el MVP.

## Contrato de la interfaz

```python
class CRMAdapter:
    async def get_customer(self, phone: str) -> Customer | None
    async def update_customer(self, phone: str, data: dict) -> bool
```
