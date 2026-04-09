# core/rag/

Capa de Retrieval-Augmented Generation. Busca información relevante para responder la pregunta del usuario.

**Por qué existe:** El agente no puede alucinar. Toda respuesta debe estar fundamentada en información real de la base de conocimiento del cliente. Esta capa implementa el patrón Autonomous RAG: busca primero en KB local, cae a búsqueda web si no encuentra, y escala a humano si sigue sin resultado útil.

## Flujo

```
query del usuario
  → búsqueda en Qdrant (colección `kb`) con score de relevancia
  → score >= threshold → devuelve contexto (fuente: kb_local)
  → score < threshold → búsqueda web (DuckDuckGo/Tavily)
  → sin resultado → flag de escalación
```

## Contrato de la interfaz

```python
class RAGProvider:
    async def retrieve(self, query: str, vertical: str) -> RAGResult
    # RAGResult: context, score, source (kb_local|web|none), latency_ms
```

## Requerimientos

- **RQ-02** — la búsqueda se filtra por `vertical` para no mezclar KBs entre negocios
- **RQ-03** — reporta `latency_ms`, `rag_score`, `source`
- **RQ-06** — fallback a web search si KB local no tiene resultado suficiente
