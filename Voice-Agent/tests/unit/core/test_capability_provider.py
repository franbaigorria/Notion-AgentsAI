"""Tests para CapabilityProvider — interfaz de acceso operativo por tenant."""
import inspect

from core.capabilities.base import CapabilityProvider, CapabilityResult


class _StubCapabilityProvider(CapabilityProvider):
    @property
    def name(self) -> str:
        return "agendar_turno"

    @property
    def description(self) -> str:
        return "Agenda un turno médico para el paciente en el calendario del tenant."

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
        if action == "book_appointment":
            return CapabilityResult(success=True, data={"booking_id": f"{tenant_id}-001"})
        return CapabilityResult(success=False, data={}, error_message=f"Acción desconocida: {action}")


# --- Firma de la interfaz ---

def test_execute_signature_uses_tenant_id_not_vertical():
    sig = inspect.signature(CapabilityProvider.execute)
    assert "tenant_id" in sig.parameters, "execute() debe aceptar tenant_id"
    assert "vertical" not in sig.parameters, "execute() no debe usar 'vertical'"


# --- Propiedades obligatorias ---

def test_name_returns_string():
    provider = _StubCapabilityProvider()
    assert isinstance(provider.name, str)
    assert provider.name == "agendar_turno"


def test_description_returns_non_empty_string():
    provider = _StubCapabilityProvider()
    assert isinstance(provider.description, str)
    assert len(provider.description) > 0


def test_parameters_returns_json_schema_dict():
    provider = _StubCapabilityProvider()
    params = provider.parameters
    assert isinstance(params, dict)
    assert "type" in params
    assert "properties" in params


# --- as_livekit_tool ---

def test_as_livekit_tool_returns_non_none():
    provider = _StubCapabilityProvider()
    tool = provider.as_livekit_tool()
    assert tool is not None


def test_as_livekit_tool_includes_name_and_description():
    provider = _StubCapabilityProvider()
    tool = provider.as_livekit_tool()
    assert tool["name"] == "agendar_turno"
    assert "Agenda" in tool["description"]


def test_as_livekit_tool_includes_parameters_schema():
    provider = _StubCapabilityProvider()
    tool = provider.as_livekit_tool()
    assert "parameters" in tool
    assert tool["parameters"]["type"] == "object"


# --- CapabilityResult ---

async def test_execute_success_returns_result_with_data():
    provider = _StubCapabilityProvider()
    result = await provider.execute(
        action="book_appointment",
        params={"especialidad": "cardiología"},
        tenant_id="clinica_del_valle",
    )
    assert result.success is True
    assert "clinica_del_valle" in result.data["booking_id"]
    assert result.error_message is None


async def test_execute_failure_returns_error_message():
    provider = _StubCapabilityProvider()
    result = await provider.execute(
        action="accion_inexistente",
        params={},
        tenant_id="clinica_del_valle",
    )
    assert result.success is False
    assert result.error_message is not None
    assert len(result.error_message) > 0
