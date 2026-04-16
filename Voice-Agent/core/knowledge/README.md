# core/knowledge/

Capa de acceso a conocimiento documental del tenant. Recupera información estática o semi-estructurada para fundamentar las respuestas del agente.

**Por qué existe:** El agente no puede alucinar. Toda respuesta debe estar fundamentada en información real de la base de conocimiento del cliente. Esta capa implementa el patrón Port/Adapter: el core define la interfaz, los adapters concretos resuelven contra Qdrant, web, o cualquier otra fuente.

## Contrato de la interfaz

```python
class KnowledgeProvider(ABC):
    async def retrieve(self, query: str, tenant_id: str) -> KnowledgeResult: ...

@dataclass
class KnowledgeResult:
    context: str                              # texto recuperado para el LLM
    score: float                              # relevancia (0.0 - 1.0)
    source: Literal["kb_local", "web", "none"]
    latency_ms: float
```

## Convención de naming en Qdrant

```
colección = kb_{tenant_id}

Ejemplo:
  tenant "clinica_del_valle"  →  colección "kb_clinica_del_valle"
  tenant "centro_medico_sur"  →  colección "kb_centro_medico_sur"
```

Cada tenant tiene su propia colección — **aislamiento garantizado sin filtros en query**.

## Flujo del adapter concreto (Qdrant)

```
query + tenant_id
  → Qdrant.search(collection="kb_{tenant_id}", score_threshold=0.75)
  → score >= 0.75  →  KnowledgeResult(source="kb_local")
  → score < 0.75   →  web fallback  →  KnowledgeResult(source="web")
  → sin resultado  →  KnowledgeResult(source="none")  →  flag de escalación
```

## Requerimientos

- **RQ-02** — la búsqueda se filtra por `tenant_id` para garantizar aislamiento total entre clientes
- **RQ-03** — reporta `latency_ms`, `score`, `source`
- **RQ-06** — fallback a web search si KB local no tiene resultado suficiente
