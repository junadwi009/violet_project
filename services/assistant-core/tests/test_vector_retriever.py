from __future__ import annotations

import pytest

from violet_assistant.rag.vector_retriever import VectorRetriever
from violet_assistant.vector.store.sqlite_vector_store import SqliteVectorStore


class _AxisEmbedder:
    """Maps 'north'->[1,0], 'east'->[0,1], anything else->[0.9,0.1]."""

    name = "mock"

    async def embed(self, texts):
        out = []
        for t in texts:
            if "north" in t:
                out.append([1.0, 0.0])
            elif "east" in t:
                out.append([0.0, 1.0])
            else:
                out.append([0.9, 0.1])
        return out


@pytest.mark.asyncio
async def test_retriever_returns_nearest_chunks(tmp_path):
    store = SqliteVectorStore(tmp_path / "k.db")
    store.initialize()
    store.upsert_doc(
        "d1",
        "a.txt",
        "h",
        1.0,
        [("north wall", [1.0, 0.0]), ("east wall", [0.0, 1.0])],
        "mock",
    )
    retriever = VectorRetriever(_AxisEmbedder(), store, model="mock")
    chunks = await retriever.retrieve("which way is north?", k=1)
    assert len(chunks) == 1
    assert chunks[0].text == "north wall"
    assert chunks[0].source == "a.txt"
