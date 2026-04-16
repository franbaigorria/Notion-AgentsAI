# core/capabilities/

Capa de acceso operativo. Ejecuta acciones transaccionales en sistemas externos del tenant.

**Por qué existe:** A diferencia de Knowledge (recuperar info) o Memory (recordar contexto), las Capabilities son las *manos* del agente: agendar un turno, verificar una cobertura, actualizar un CRM. Cada tenant conecta a sus propios sistemas — Google Calendar de una clínica, Docplanner de otra. El Port/Adapter pattern permite que el orchestrator trabaje con la misma interfaz sin saber qué sistema hay detrás.

## Contrato de la interfaz

```python
class CapabilityProvider(ABC):

    @property @abstractmethod
    def name(self) -> str:
        """Nombre único del tool — usado por el LLM para identificarlo."""

    @property @abstractmethod
    def description(self) -> str:
        """Descripción en lenguaje natural — el LLM la usa para decidir cuándo invocar el tool."""

    @property @abstractmethod
    def parameters(self) -> dict:
        """JSON Schema de los parámetros que acepta el tool."""

    @abstractmethod
    async def execute(self, action: str, params: dict, tenant_id: str) -> CapabilityResult:
        """Ejecuta la acción en el sistema externo del tenant.
        NUNCA debe lanzar excepción — siempre retornar un CapabilityResult.
        """

    def as_livekit_tool(self) -> dict:
        """Concreto en base class. Construye el descriptor del tool para LiveKit."""
        return {"name": self.name, "description": self.description, "parameters": self.parameters}


@dataclass
class CapabilityResult:
    success: bool
    data: dict[str, Any]
    error_message: str | None = None
```

## Registro de capabilities en el orchestrator

El orchestrator registra las capabilities activas del tenant como function_tools del LLM:

```python
tools = [cap.as_livekit_tool() for cap in tenant.capabilities]

session = AgentSession(
    instructions=tenant.persona_prompt,
    tools=tools,
)
```

El LLM recibe `name` y `description` de cada tool y decide cuándo invocar cada uno en función del intent del usuario.

## Declaración de capabilities en integrations.yaml

Cada tenant declara en su `integrations.yaml` qué capabilities activa y cómo configurarlas:

```yaml
# verticals/clinica/integrations.yaml (template)
capabilities:
  - type: google_calendar
    action: book_appointment
    config:
      calendar_id: "${TENANT_CALENDAR_ID}"   # se resuelve desde DB del tenant

  - type: coverage_checker
    action: verify_coverage
    config:
      api_url: "${TENANT_COVERAGE_API}"
```

El `tenant_id` se pasa en `execute()` para que el adapter pueda conectar al sistema correcto del cliente — cada tenant tiene sus propias credenciales y endpoints.

## Implementar un nuevo adapter

```python
# adapters/capabilities/google_calendar.py
class GoogleCalendarCapability(CapabilityProvider):

    @property
    def name(self) -> str:
        return "agendar_turno"

    @property
    def description(self) -> str:
        return "Agenda un turno médico para el paciente en el calendario del consultorio."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "especialidad": {"type": "string"},
                "fecha": {"type": "string", "format": "date"},
            },
            "required": ["especialidad"],
        }

    async def execute(self, action: str, params: dict, tenant_id: str) -> CapabilityResult:
        credentials = await load_tenant_credentials(tenant_id)
        # ... lógica de Google Calendar con las credenciales del tenant
        return CapabilityResult(success=True, data={"booking_id": "..."})
```

## Requerimientos

- **RQ-04** — cada capability es aislada por `tenant_id` — un adapter usa las credenciales del tenant correcto
- **RQ-05** — `execute()` nunca lanza excepción; siempre retorna `CapabilityResult` con `success=False` y `error_message` en caso de error
- **RQ-07** — `as_livekit_tool()` retorna un descriptor válido para registro en LiveKit AgentSession
