"""Tests para KnowledgeProvider — interfaz de acceso a conocimiento por tenant."""
import inspect

from core.knowledge.base import KnowledgeProvider, KnowledgeResult


class _StubKnowledgeProvider(KnowledgeProvider):
    async def retrieve(self, query: str, tenant_id: str) -> KnowledgeResult:
        return KnowledgeResult(
            context=f"resultado para tenant:{tenant_id} query:{query}",
            score=0.92,
            source="kb_local",
            latency_ms=80.0,
        )


# --- KnowledgeResult ---

def test_knowledge_result_source_kb_local():
    result = KnowledgeResult(context="info", score=0.9, source="kb_local", latency_ms=50.0)
    assert result.source == "kb_local"
    assert result.score == 0.9


def test_knowledge_result_source_none():
    result = KnowledgeResult(context="", score=0.0, source="none", latency_ms=0.0)
    assert result.source == "none"
    assert result.context == ""


# --- Firma de la interfaz ---

def test_retrieve_signature_uses_tenant_id_not_vertical():
    sig = inspect.signature(KnowledgeProvider.retrieve)
    assert "tenant_id" in sig.parameters, "retrieve() debe aceptar tenant_id"
    assert "vertical" not in sig.parameters, "retrieve() no debe usar 'vertical' — usar 'tenant_id'"


# --- Comportamiento concreto ---

async def test_retrieve_returns_kb_local_result_for_known_tenant():
    provider = _StubKnowledgeProvider()
    result = await provider.retrieve(query="horarios", tenant_id="clinica_del_valle")
    assert result.source == "kb_local"
    assert result.score > 0.0
    assert "clinica_del_valle" in result.context


async def test_retrieve_isolates_by_tenant_id():
    """Tenants distintos producen resultados distintos — el tenant_id llega al provider."""
    provider = _StubKnowledgeProvider()
    result_a = await provider.retrieve(query="horarios", tenant_id="clinica_a")
    result_b = await provider.retrieve(query="horarios", tenant_id="clinica_b")
    assert "clinica_a" in result_a.context
    assert "clinica_b" in result_b.context
    assert result_a.context != result_b.context
