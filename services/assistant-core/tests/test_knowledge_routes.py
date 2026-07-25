from __future__ import annotations

import pytest

from violet_assistant.knowledge.indexer import KnowledgeIndexer
from violet_assistant.routes.knowledge import ReindexRequest, create_knowledge_router
from violet_assistant.vector.embeddings.mock_embedder import MockEmbedder
from violet_assistant.vector.store.sqlite_vector_store import SqliteVectorStore


def _endpoint(router, method):
    for route in router.routes:
        if method in route.methods:
            return route.endpoint
    raise KeyError(method)


@pytest.mark.asyncio
async def test_knowledge_status_and_reindex(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "a.txt").write_text("hello", encoding="utf-8")
    store = SqliteVectorStore(tmp_path / "k.db")
    store.initialize()
    indexer = KnowledgeIndexer(MockEmbedder(), store, kdir)
    router = create_knowledge_router(indexer, store, str(kdir), "mock")

    before = await _endpoint(router, "GET")()
    assert before["doc_count"] == 0
    assert before["enabled"] is True

    report = await _endpoint(router, "POST")(ReindexRequest(full=False))
    assert report["indexed"] == 1

    after = await _endpoint(router, "GET")()
    assert after["doc_count"] == 1
    assert after["chunk_count"] >= 1


@pytest.mark.asyncio
async def test_reindex_409_when_no_indexer():
    from fastapi import HTTPException

    router = create_knowledge_router(None, None, "knowledge", "none")
    with pytest.raises(HTTPException) as exc:
        await _endpoint(router, "POST")(ReindexRequest(full=False))
    assert exc.value.status_code == 409
