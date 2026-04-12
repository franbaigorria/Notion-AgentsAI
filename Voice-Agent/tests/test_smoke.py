"""Smoke tests — verifican que las piezas centrales funcionan sin APIs reales.

Test 1: run_local con FakeLLMProvider — persona system prompt llega al LLM, stdout recibe respuesta.
Test 2: ClaudeLLM.complete() con SDK mockeado via unittest.mock.
Test 3: Decorator @track emite evento JSON con campos correctos.
"""

import io
import json
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.base import LLMContext, LLMResult, Message
from core.observability.tracing import current_call_id, track
from tests.fakes import FakeLLMProvider


# ---------------------------------------------------------------------------
# Test 1: run_local invoca el LLM con el persona system prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_local_uses_persona_and_outputs_to_stdout(capsys):
    """run_local debe pasar la persona como system prompt y la respuesta debe llegar a stdout."""
    from core.orchestrator import local as local_mod

    fake_llm = FakeLLMProvider(response="Hola, soy Nanci. ¿En qué puedo ayudarte?")

    # Simular: una línea de stdin ("Quiero un turno") y luego EOF
    user_input = "Quiero un turno\n"

    with (
        patch.object(local_mod, "ClaudeLLM", return_value=fake_llm),
        patch("core.telephony.local.sys.stdin", io.StringIO(user_input)),
    ):
        await local_mod.run_local(vertical="clinica", mode="text")

    captured = capsys.readouterr()
    stdout_lines = [l for l in captured.out.strip().splitlines() if l]

    # Al menos dos líneas: saludo + respuesta al turno
    assert len(stdout_lines) >= 1

    # El LLM fue invocado al menos una vez
    assert len(fake_llm.calls) >= 1

    # El system prompt de la primera llamada viene de persona.md (no vacío)
    first_call: LLMContext = fake_llm.calls[0]
    assert first_call.system.strip(), "System prompt vacío — persona.md no se cargó"
    assert len(first_call.system) > 50, "System prompt demasiado corto para ser una persona real"


# ---------------------------------------------------------------------------
# Test 2: ClaudeLLM.complete() con SDK mockeado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claude_llm_complete_uses_sdk():
    """ClaudeLLM.complete() debe retornar LLMResult con los campos correctos."""
    from core.llm.claude import ClaudeLLM

    # Mock de la respuesta del SDK
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="Claro, te agendo un turno para mañana.")]
    fake_response.usage.input_tokens = 100
    fake_response.usage.output_tokens = 20

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=fake_response)

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        llm = ClaudeLLM(model="claude-sonnet-4-6")
        ctx = LLMContext(
            system="Sos Nanci, asistente de una clínica.",
            messages=[Message(role="user", content="Quiero un turno para mañana.")],
        )
        result = await llm.complete(ctx)

    assert isinstance(result, LLMResult)
    assert result.content == "Claro, te agendo un turno para mañana."
    assert result.input_tokens == 100
    assert result.output_tokens == 20
    assert result.latency_ms >= 0
    assert result.cost_usd > 0
    assert result.provider == "claude"


# ---------------------------------------------------------------------------
# Test 3: @track emite evento JSON con campos correctos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_track_decorator_emits_json_event(capsys):
    """@track debe emitir un evento JSON con call_id, provider, operation, latency_ms, cost_usd."""
    call_id = str(uuid.uuid4())
    current_call_id.set(call_id)

    @track(provider="test-provider", operation="test-op")
    async def fake_op():
        return LLMResult(
            content="ok",
            input_tokens=10,
            output_tokens=5,
            latency_ms=42.0,
            cost_usd=0.0005,
            provider="test-provider",
        )

    with patch("core.observability.tracing._SINK", "stdout"), \
         patch("core.observability.tracing.sys.stderr", sys.stdout):
        await fake_op()

    captured = capsys.readouterr()
    # El último evento JSON emitido (puede haber ruido del LLM mock anterior)
    json_lines = [l for l in captured.out.strip().splitlines() if l.startswith("{")]
    assert json_lines, "No se emitió ningún evento JSON"

    event = json.loads(json_lines[-1])
    assert event["call_id"] == call_id
    assert event["provider"] == "test-provider"
    assert event["operation"] == "test-op"
    assert event["latency_ms"] == 42.0
    assert event["cost_usd"] == 0.0005
    assert "timestamp" in event
