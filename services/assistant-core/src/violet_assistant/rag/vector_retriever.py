from __future__ import annotations

from violet_assistant.rag.base import Chunk


class VectorRetriever:
    name = "vector"

    def __init__(self, embedder, store, model: str) -> None:
        self.embedder = embedder
        self.store = store
        self.model = model

    async def retrieve(self, query: str, k: int = 4) -> list[Chunk]:
        vectors = await self.embedder.embed([query])
        if not vectors:
            return []
        rows = self.store.query(vectors[0], k, self.model)
        return [
            Chunk(
                text=row["text"],
                source=row["source"],
                score=float(row["score"]),
                metadata={"chunk_index": str(row["chunk_index"])},
            )
            for row in rows
        ]
