from __future__ import annotations

import pytest

from violet_assistant.knowledge.indexer import KnowledgeIndexer
from violet_assistant.knowledge.sources.local_folder import LocalFolderSource
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
    indexer = KnowledgeIndexer(MockEmbedder(), store, [LocalFolderSource(kdir)])
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


@pytest.mark.asyncio
async def test_status_includes_sources(tmp_path):
    from violet_assistant.config import load_settings

    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    store = SqliteVectorStore(tmp_path / "k.db")
    store.initialize()
    src = LocalFolderSource(kdir)
    indexer = KnowledgeIndexer(MockEmbedder(), store, [src])
    router = create_knowledge_router(
        indexer, store, str(kdir), "mock", [src], None, load_settings(tmp_path)
    )
    body = await _endpoint(router, "GET")()
    assert any(s["name"] == "local" for s in body["sources"])


@pytest.mark.asyncio
async def test_reindex_source_filter(tmp_path):
    from violet_assistant.config import load_settings

    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "a.txt").write_text("hi there", encoding="utf-8")
    store = SqliteVectorStore(tmp_path / "k.db")
    store.initialize()
    src = LocalFolderSource(kdir)
    indexer = KnowledgeIndexer(MockEmbedder(), store, [src])
    router = create_knowledge_router(
        indexer, store, str(kdir), "mock", [src], None, load_settings(tmp_path)
    )
    report = await _endpoint(router, "POST")(ReindexRequest(full=False, source="local"))
    assert report["sources"]["local"]["indexed"] == 1


@pytest.mark.asyncio
async def test_gdrive_status_not_configured_without_source():
    router = create_knowledge_router(None, None, "knowledge", "none")
    body = await _gdrive_status_ep(router)()
    assert body["detail"] == "not_configured"


def _gdrive_status_ep(router):
    for route in router.routes:
        if route.path == "/api/knowledge/gdrive/status":
            return route.endpoint
    raise KeyError("gdrive/status")


@pytest.mark.asyncio
async def test_status_includes_auto_sync(tmp_path):
    from violet_assistant.config import load_settings
    from violet_assistant.knowledge.auto_sync import AutoSyncScheduler
    from violet_assistant.preferences.store import PreferencesStore

    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    store = SqliteVectorStore(tmp_path / "k.db")
    store.initialize()
    src = LocalFolderSource(kdir)
    indexer = KnowledgeIndexer(MockEmbedder(), store, [src])
    settings = load_settings(tmp_path)
    scheduler = AutoSyncScheduler(indexer, PreferencesStore(tmp_path / "p.json"), settings)
    router = create_knowledge_router(
        indexer, store, str(kdir), "mock", [src], None, settings, scheduler
    )
    body = await _endpoint(router, "GET")()
    assert body["auto_sync"]["enabled"] is False
    assert body["auto_sync"]["interval"] == 30


@pytest.mark.asyncio
async def test_create_app_does_not_leave_unawaited_reindex(tmp_path, monkeypatch):
    """Regression: the startup scan must not be run from sync create_app().

    This test is async on purpose: it reproduces uvicorn's condition (an event
    loop already running in this thread). Under that condition the old code —
    `asyncio.new_event_loop().run_until_complete(indexer.reindex())` — raises
    "Cannot run the event loop while another loop is running", gets swallowed by
    a bare `except`, and silently skips the scan, leaving the coroutine
    un-awaited. Called from a sync test it would wrongly pass.
    """
    import gc
    import warnings
    from pathlib import Path

    from violet_assistant.config import load_settings
    from violet_assistant.main import create_app

    # repo_root must be the real repo (migration SQL lives there); every data
    # path is redirected into tmp so the test touches nothing real.
    repo_root = Path(__file__).resolve().parents[3]
    monkeypatch.setenv("RAG_PROVIDER", "vector")
    monkeypatch.setenv("KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("KNOWLEDGE_DB", str(tmp_path / "knowledge.db"))
    monkeypatch.setenv("KNOWLEDGE_SCAN_ON_STARTUP", "true")
    monkeypatch.setenv("MEMORY_DIR", str(tmp_path / "memory"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'violet.db'}")
    (tmp_path / "knowledge").mkdir()

    settings = load_settings(repo_root)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        create_app(settings)
        gc.collect()  # the "never awaited" warning fires when the coro is collected
    never_awaited = [w for w in caught if "never awaited" in str(w.message)]
    assert never_awaited == [], f"create_app left an un-awaited coroutine: {never_awaited}"
