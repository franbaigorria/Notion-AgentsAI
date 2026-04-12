"""RAG local — Qdrant in-memory + FastEmbed.

Sin servidor, sin Docker. Corre dentro del proceso Python.
Para producción: cambiar QdrantClient(":memory:") por QdrantClient("localhost", port=6333).

El modelo de embeddings (BAAI/bge-m3) se descarga automáticamente en el primer uso
y se cachea en ~/.cache/fastembed. Descarga única ~570MB.

Uso:
    from core.rag.qdrant import QdrantRAG
    from pathlib import Path

    rag = QdrantRAG.from_kb_dir(Path("verticals/clinica/kb"), vertical="clinica")
    result = await rag.retrieve("qué especialidades tienen", vertical="clinica")
    print(result.context)
"""

import re
import time
import warnings
from pathlib import Path

from qdrant_client import QdrantClient

from .base import RAGProvider, RAGResult

# Umbral de score mínimo para considerar un chunk relevante.
# Por debajo de este valor, el RAG retorna source="none" y context vacío.
_SCORE_THRESHOLD = 0.28
_TOP_K = 3

# Modelo específico para español — mejor opción disponible en esta versión de qdrant-client.
# Descarga única ~270MB, se cachea automáticamente en ~/.cache/fastembed.
_EMBEDDING_MODEL = "jinaai/jina-embeddings-v2-base-es"


def _chunk_markdown(text: str) -> list[str]:
    """Divide el markdown en chunks por sección (##).

    Incluye el heading en cada chunk para que el embedding capture el tema.
    Secciones vacías o muy cortas se descartan.
    """
    sections = re.split(r"\n(?=##\s)", text.strip())
    return [s.strip() for s in sections if len(s.strip()) > 30]


class QdrantRAG(RAGProvider):
    """RAG local con Qdrant in-memory y FastEmbed.

    - ingest_texts(): ingesta chunks en la colección del vertical
    - retrieve(): busca contexto relevante para una query
    - from_kb_dir(): factory que lee y ingesta todos los .md de un directorio
    """

    def __init__(self, embedding_model: str = _EMBEDDING_MODEL):
        print(
            f"[RAG] Cargando modelo de embeddings '{embedding_model}'...\n"
            "      (primer vez: descarga ~270MB, se cachea automáticamente en ~/.cache/fastembed)",
            flush=True,
        )
        self._embedding_model = embedding_model
        self._client = QdrantClient(":memory:")
        self._client.set_model(embedding_model)
        self._collections: set[str] = set()

    def ingest_texts(self, vertical: str, chunks: list[str], source_id: str) -> None:
        """Ingesta una lista de chunks en la colección del vertical."""
        collection = f"kb_{vertical}"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self._client.add(
                collection_name=collection,
                documents=chunks,
                metadata=[{"source": source_id, "vertical": vertical}] * len(chunks),
            )
        self._collections.add(collection)
        print(f"[RAG] Ingestados {len(chunks)} chunks de '{source_id}' → colección '{collection}'")

    async def retrieve(self, query: str, vertical: str) -> RAGResult:
        """Busca los chunks más relevantes para la query en la KB del vertical."""
        collection = f"kb_{vertical}"

        if collection not in self._collections:
            return RAGResult(context="", score=0.0, source="none", latency_ms=0.0)

        start = time.monotonic()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            results = self._client.query(
                collection_name=collection,
                query_text=query,
                limit=_TOP_K,
            )
        latency_ms = (time.monotonic() - start) * 1000

        if not results or results[0].score < _SCORE_THRESHOLD:
            return RAGResult(context="", score=0.0, source="none", latency_ms=latency_ms)

        relevant = [r for r in results if r.score >= _SCORE_THRESHOLD]
        context = "\n\n---\n\n".join(r.document for r in relevant)

        return RAGResult(
            context=context,
            score=results[0].score,
            source="kb_local",
            latency_ms=latency_ms,
        )

    @classmethod
    def from_kb_dir(cls, kb_dir: Path, vertical: str) -> "QdrantRAG":
        """Crea una instancia e ingesta todos los archivos .md del directorio."""
        if not kb_dir.exists():
            raise FileNotFoundError(f"Directorio KB no encontrado: {kb_dir}")

        rag = cls()
        md_files = sorted(kb_dir.glob("*.md"))

        if not md_files:
            raise FileNotFoundError(f"No hay archivos .md en {kb_dir}")

        for path in md_files:
            text = path.read_text(encoding="utf-8")
            chunks = _chunk_markdown(text)
            rag.ingest_texts(vertical, chunks, source_id=path.stem)

        return rag
