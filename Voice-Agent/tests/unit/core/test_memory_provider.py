"""Tests para MemoryProvider — interfaz de memoria persistente por tenant."""
import inspect

from core.memory.base import Memory, MemoryProvider


class _StubMemoryProvider(MemoryProvider):
    def __init__(self):
        self._store: dict[str, list[Memory]] = {}

    async def get(self, user_id: str, tenant_id: str) -> list[Memory]:
        key = f"{tenant_id}:{user_id}"
        return self._store.get(key, [])

    async def save(self, user_id: str, tenant_id: str, transcript: str) -> None:
        key = f"{tenant_id}:{user_id}"
        self._store.setdefault(key, []).append(Memory(key=user_id, value=transcript))


# --- Firma de la interfaz ---

def test_get_signature_uses_tenant_id_not_vertical():
    sig = inspect.signature(MemoryProvider.get)
    assert "tenant_id" in sig.parameters, "get() debe aceptar tenant_id"
    assert "vertical" not in sig.parameters, "get() no debe usar 'vertical'"


def test_save_signature_uses_tenant_id_not_vertical():
    sig = inspect.signature(MemoryProvider.save)
    assert "tenant_id" in sig.parameters, "save() debe aceptar tenant_id"
    assert "vertical" not in sig.parameters, "save() no debe usar 'vertical'"


# --- Comportamiento concreto ---

async def test_get_returns_empty_list_for_unknown_user():
    provider = _StubMemoryProvider()
    result = await provider.get(user_id="+5491155443322", tenant_id="clinica_a")
    assert result == []


async def test_save_then_get_returns_stored_memory():
    provider = _StubMemoryProvider()
    await provider.save(
        user_id="+5491155443322",
        tenant_id="clinica_a",
        transcript="quiero un turno con el Dr. García",
    )
    memories = await provider.get(user_id="+5491155443322", tenant_id="clinica_a")
    assert len(memories) == 1
    assert "García" in memories[0].value


async def test_memory_isolated_per_tenant():
    """El mismo usuario en dos tenants distintos tiene memoria separada."""
    provider = _StubMemoryProvider()
    await provider.save(
        user_id="+5491155443322",
        tenant_id="clinica_a",
        transcript="turno con Dr. García",
    )
    memories_b = await provider.get(user_id="+5491155443322", tenant_id="clinica_b")
    assert memories_b == [], "Clinica B no debe ver la memoria de Clinica A"
