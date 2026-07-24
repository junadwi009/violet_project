from __future__ import annotations

from violet_assistant.config import Settings
from violet_assistant.rag.base import Retriever
from violet_assistant.rag.no_op_retriever import NoOpRetriever


NO_OP_PROVIDERS = {"none", "off", "mock", ""}


def create_retriever(settings: Settings) -> Retriever:
    """Build the active retriever from ``RAG_PROVIDER``.

    Track 2 adds real providers (e.g. ``vector``) here as sibling branches, each backed by
    the Track 3 vector store. Unknown values fail loudly rather than silently disabling RAG.
    """
    provider = settings.rag_provider.strip().lower()
    if provider in NO_OP_PROVIDERS:
        return NoOpRetriever()

    supported = sorted(NO_OP_PROVIDERS - {""})
    raise ValueError(
        f"Unsupported RAG_PROVIDER={settings.rag_provider!r}. "
        f"Supported values: {', '.join(supported)} (Track 2 adds more)."
    )
