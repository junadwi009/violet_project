from __future__ import annotations

from violet_assistant.config import Settings
from violet_assistant.rag.base import Retriever
from violet_assistant.rag.no_op_retriever import NoOpRetriever


NO_OP_PROVIDERS = {"none", "off", "mock", ""}


def create_retriever(settings: Settings) -> Retriever:
    """Build the active retriever from ``RAG_PROVIDER``.

    ``vector`` activates the SQLite-backed knowledge base (embed → cosine).
    Unknown values fail loudly rather than silently disabling RAG.
    """
    provider = settings.rag_provider.strip().lower()
    if provider in NO_OP_PROVIDERS:
        return NoOpRetriever()
    if provider == "vector":
        from violet_assistant.rag.vector_retriever import VectorRetriever
        from violet_assistant.vector.embeddings.factory import create_embedder
        from violet_assistant.vector.store.sqlite_vector_store import SqliteVectorStore

        store = SqliteVectorStore(settings.knowledge_db)
        store.initialize()
        embedder = create_embedder(settings)
        return VectorRetriever(embedder, store, model=embedder.name)

    supported = sorted((NO_OP_PROVIDERS - {""}) | {"vector"})
    raise ValueError(
        f"Unsupported RAG_PROVIDER={settings.rag_provider!r}. "
        f"Supported values: {', '.join(supported)}."
    )
