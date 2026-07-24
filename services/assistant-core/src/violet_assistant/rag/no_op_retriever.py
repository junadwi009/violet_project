from __future__ import annotations

from violet_assistant.rag.base import Chunk


class NoOpRetriever:
    """Default retriever: returns no context, so chat behaves exactly as pre-RAG."""

    name = "none"

    async def retrieve(self, query: str, k: int = 4) -> list[Chunk]:
        return []
