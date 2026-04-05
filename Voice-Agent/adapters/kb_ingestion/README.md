# adapters/kb_ingestion/

Pipeline de ingesta de la base de conocimiento. Toma fuentes de datos del cliente y las carga en Qdrant.

**Por qué existe:** Cada vertical tiene su propia KB (el sitio de la clínica, sus PDFs de aranceles, su lista de médicos). Este adapter es el encargado de transformar esas fuentes en embeddings vectoriales y cargarlos en la colección `kb` de Qdrant para que el RAG pueda consultarlos.

## Implementaciones planificadas

| Archivo | Fuente | Herramienta |
|---------|--------|-------------|
| `firecrawl.py` | Sitios web | Firecrawl → chunks → FastEmbed → Qdrant |
| `pdf.py` | Documentos PDF | LangChain PDF loader → chunks → FastEmbed → Qdrant |

## Flujo general

```
fuente (URL o archivo)
  → extracción de texto (Firecrawl o LangChain)
  → chunking
  → embeddings (FastEmbed — local, sin costo de API)
  → upsert en Qdrant (colección `kb`, namespace del vertical)
```

## Requerimientos

- **RQ-02** — la ingesta se hace por vertical; cada documento se indexa bajo el namespace del vertical para que el RAG no mezcle KBs
