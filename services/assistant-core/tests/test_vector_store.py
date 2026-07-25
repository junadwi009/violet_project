from __future__ import annotations

from violet_assistant.vector.store.sqlite_vector_store import SqliteVectorStore


def _store(tmp_path):
    store = SqliteVectorStore(tmp_path / "knowledge.db")
    store.initialize()
    return store


def test_upsert_query_ranks_nearest_first(tmp_path):
    store = _store(tmp_path)
    store.upsert_doc(
        doc_id="d1",
        path="a.txt",
        version="h1",
        mtime=1.0,
        chunks=[("north", [1.0, 0.0]), ("east", [0.0, 1.0])],
        model="mock",
    )
    results = store.query([0.9, 0.1], k=2, model="mock")
    assert results[0]["text"] == "north"
    assert results[0]["source"] == "a.txt"
    assert results[0]["score"] >= results[1]["score"]


def test_query_excludes_other_models(tmp_path):
    store = _store(tmp_path)
    store.upsert_doc("d1", "a.txt", "h", 1.0, [("x", [1.0, 0.0])], model="other")
    assert store.query([1.0, 0.0], k=3, model="mock") == []


def test_upsert_replaces_chunks_and_delete_removes(tmp_path):
    store = _store(tmp_path)
    store.upsert_doc(
        "d1", "a.txt", "h1", 1.0, [("x", [1.0, 0.0]), ("y", [0.0, 1.0])], "mock"
    )
    store.upsert_doc("d1", "a.txt", "h2", 2.0, [("z", [1.0, 0.0])], "mock")
    assert store.stats()["chunk_count"] == 1
    assert store.doc_by_path("a.txt")["hash"] == "h2"
    store.delete_doc("d1")
    assert store.stats() == {"doc_count": 0, "chunk_count": 0}


def test_origin_scoped_docs_and_delete_missing(tmp_path):
    store = _store(tmp_path)
    store.upsert_doc("local:a.txt", "a.txt", "v1", 1.0, [("x", [1.0, 0.0])], "mock", origin="local")
    store.upsert_doc("gdrive:1", "Drive/a", "v9", 1.0, [("y", [0.0, 1.0])], "mock", origin="gdrive")
    assert store.stats()["doc_count"] == 2
    assert store.stats(origin="gdrive")["doc_count"] == 1
    assert {d["path"] for d in store.list_docs(origin="local")} == {"a.txt"}
    removed = store.delete_missing("gdrive", seen_ids=set())
    assert removed == 1
    assert store.stats(origin="local")["doc_count"] == 1
    assert store.doc_by_id("local:a.txt")["version"] == "v1"


def test_upsert_updates_version_and_incremental_key(tmp_path):
    store = _store(tmp_path)
    store.upsert_doc("gdrive:1", "Drive/a", "v1", 1.0, [("y", [0.0, 1.0])], "mock", origin="gdrive")
    store.upsert_doc("gdrive:1", "Drive/a", "v2", 2.0, [("z", [0.0, 1.0])], "mock", origin="gdrive")
    assert store.doc_by_id("gdrive:1")["version"] == "v2"
    assert store.stats()["chunk_count"] == 1
