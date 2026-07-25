from __future__ import annotations

import pytest

from violet_assistant.knowledge.indexer import KnowledgeIndexer
from violet_assistant.vector.embeddings.mock_embedder import MockEmbedder
from violet_assistant.vector.store.sqlite_vector_store import SqliteVectorStore


def _indexer(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    store = SqliteVectorStore(tmp_path / "knowledge.db")
    store.initialize()
    return KnowledgeIndexer(MockEmbedder(), store, kdir), kdir, store


@pytest.mark.asyncio
async def test_reindex_indexes_and_is_incremental(tmp_path):
    indexer, kdir, store = _indexer(tmp_path)
    (kdir / "a.txt").write_text("hello knowledge base", encoding="utf-8")
    first = await indexer.reindex()
    assert first["indexed"] == 1 and first["chunks"] >= 1
    second = await indexer.reindex()
    assert second["indexed"] == 0 and second["skipped"] == 1


@pytest.mark.asyncio
async def test_reindex_removes_deleted_files(tmp_path):
    indexer, kdir, store = _indexer(tmp_path)
    f = kdir / "a.txt"
    f.write_text("content", encoding="utf-8")
    await indexer.reindex()
    f.unlink()
    report = await indexer.reindex()
    assert report["removed"] == 1
    assert store.stats()["doc_count"] == 0


@pytest.mark.asyncio
async def test_reindex_skips_unsupported_extensions(tmp_path):
    indexer, kdir, store = _indexer(tmp_path)
    (kdir / "bad.xyz").write_text("unsupported", encoding="utf-8")
    report = await indexer.reindex()
    assert report["indexed"] == 0 and report["errors"] == []


@pytest.mark.asyncio
async def test_reindex_records_error_for_unreadable_supported_file(tmp_path):
    indexer, kdir, store = _indexer(tmp_path)
    # Supported extension but no readable text → extract_text raises → captured.
    (kdir / "empty.txt").write_text("   ", encoding="utf-8")
    report = await indexer.reindex()
    assert report["indexed"] == 0
    assert len(report["errors"]) == 1
    assert report["errors"][0]["path"] == "empty.txt"


@pytest.mark.asyncio
async def test_reindex_full_rebuild(tmp_path):
    indexer, kdir, store = _indexer(tmp_path)
    (kdir / "a.txt").write_text("hello", encoding="utf-8")
    await indexer.reindex()
    report = await indexer.reindex(full=True)
    assert report["indexed"] == 1  # full ignores the hash-skip
