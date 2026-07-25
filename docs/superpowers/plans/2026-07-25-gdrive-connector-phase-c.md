# Google Drive Connector (Knowledge Base Phase C) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google Drive (incl. Shared Drives) as a read-only knowledge source that feeds the existing chunk→embed→store pipeline, via a source abstraction and OAuth.

**Architecture:** Introduce a `KnowledgeSource` protocol; refactor the local scan into `LocalFolderSource`; add `GoogleDriveSource` (OAuth, Drive v3, export/download). `KnowledgeIndexer` iterates a list of sources with per-origin incremental sync + cleanup. The vector store gains `origin`/`version` columns. Google libs are lazy-imported so core Violet still boots without them.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, stdlib `sqlite3`; Google libs (`google-api-python-client`, `google-auth`, `google-auth-oauthlib`) lazy-imported; pytest with injected fakes (no network). React 18 + TS + Vite.

## Global Constraints

- Python `>=3.11`; backend root `services/assistant-core/src/violet_assistant`.
- Run tests from repo root: `python -m pytest -q`. Async tests: `@pytest.mark.asyncio`.
- Test routers by awaiting endpoint callables directly (no `TestClient`/httpx).
- **No test may import Google libraries.** `GoogleDriveSource` takes an injected `service`; `gdrive_auth` lazy-imports and its lib-free paths (missing token → None, revoke) are what's unit-tested.
- Drive is **read-only** (`drive.readonly`); Violet never writes to Drive.
- Secrets (OAuth client secrets, `data/gdrive_token.json`) never committed. `data/` is already gitignored.
- Drive is active only when `KNOWLEDGE_SOURCES` includes `gdrive` AND `GDRIVE_FOLDER_ID` + `GOOGLE_OAUTH_CLIENT_SECRETS` are set. Default `KNOWLEDGE_SOURCES=local` keeps everything as today.
- Preserve backward compatibility: existing `data/knowledge.db` rows migrate to `origin='local'`, `version=<existing hash>`.
- Every unit: tests + a `logs/{update}_{YYYY-MM-DD}_log.md` entry (template `logs/_TEMPLATE.md`) before committing. Date 2026-07-25.
- Frontend verified with `cd apps/web-client && npm run build`.

---

### Task 1: Vector store — `origin`/`version` columns + new methods

**Files:**
- Modify: `services/assistant-core/src/violet_assistant/vector/store/sqlite_vector_store.py`
- Modify: `services/assistant-core/src/violet_assistant/vector/store/base.py`
- Test: `services/assistant-core/tests/test_vector_store.py` (extend)

**Interfaces:**
- Produces: `SqliteVectorStore.upsert_doc(doc_id, path, version, mtime, chunks, model, origin)`; `doc_by_id(doc_id) -> dict | None`; `delete_missing(origin, seen_ids: set[str]) -> int`; `list_docs(origin: str | None = None)`; `stats(origin: str | None = None)`. Migrates old DBs (adds `origin`/`version`, backfills).
- Note: `upsert_doc` replaces the old `hash` param with `version` and adds `origin`; `doc_by_path` is retained for the migration/back-compat but `doc_by_id` is the new incremental key.

- [ ] **Step 1: Write failing tests (extend test_vector_store.py)**

```python
# append to services/assistant-core/tests/test_vector_store.py
def test_origin_scoped_docs_and_delete_missing(tmp_path):
    store = _store(tmp_path)
    store.upsert_doc("local:a.txt", "a.txt", "v1", 1.0, [("x", [1.0, 0.0])], "mock", origin="local")
    store.upsert_doc("gdrive:1", "Drive/a", "v9", 1.0, [("y", [0.0, 1.0])], "mock", origin="gdrive")
    assert store.stats()["doc_count"] == 2
    assert store.stats(origin="gdrive")["doc_count"] == 1
    assert {d["path"] for d in store.list_docs(origin="local")} == {"a.txt"}
    # cleanup only removes missing docs of that origin
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_vector_store.py -q`
Expected: FAIL (`upsert_doc` has no `origin`/`version`; `doc_by_id`/`delete_missing`/`stats(origin=)` missing).

- [ ] **Step 3: Update the schema + migration**

In `sqlite_vector_store.py`, change the `knowledge_docs` part of `_SCHEMA` to include the new columns (fresh DBs):

```python
CREATE TABLE IF NOT EXISTS knowledge_docs (
  doc_id TEXT PRIMARY KEY,
  path TEXT UNIQUE,
  hash TEXT,
  version TEXT,
  origin TEXT DEFAULT 'local',
  mtime REAL,
  chunk_count INTEGER,
  status TEXT,
  indexed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

Add a migration run inside `initialize()` after `executescript(_SCHEMA)`:

```python
    def _migrate(self, connection) -> None:
        cols = {row["name"] for row in connection.execute("PRAGMA table_info(knowledge_docs)")}
        if "version" not in cols:
            connection.execute("ALTER TABLE knowledge_docs ADD COLUMN version TEXT")
            connection.execute("UPDATE knowledge_docs SET version = hash WHERE version IS NULL")
        if "origin" not in cols:
            connection.execute("ALTER TABLE knowledge_docs ADD COLUMN origin TEXT DEFAULT 'local'")
            connection.execute("UPDATE knowledge_docs SET origin = 'local' WHERE origin IS NULL")
```

And call it:

```python
    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            self._migrate(connection)
```

- [ ] **Step 4: Update `upsert_doc` + add new methods**

Replace `upsert_doc` signature/body:

```python
    def upsert_doc(self, doc_id, path, version, mtime, chunks, model, origin="local") -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM knowledge_chunks WHERE doc_id = ?", (doc_id,))
            connection.execute(
                """INSERT INTO knowledge_docs
                     (doc_id, path, hash, version, origin, mtime, chunk_count, status, indexed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'indexed', CURRENT_TIMESTAMP)
                   ON CONFLICT(doc_id) DO UPDATE SET
                     path=excluded.path, hash=excluded.hash, version=excluded.version,
                     origin=excluded.origin, mtime=excluded.mtime,
                     chunk_count=excluded.chunk_count, status='indexed',
                     indexed_at=CURRENT_TIMESTAMP""",
                (doc_id, path, version, version, origin, mtime, len(chunks)),
            )
            for index, (text, vector) in enumerate(chunks):
                connection.execute(
                    """INSERT INTO knowledge_chunks
                         (id, doc_id, source, chunk_index, text, embedding, model, dim)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (str(uuid4()), doc_id, path, index, text, _to_blob(vector), model, len(vector)),
                )
```

(Note: `path` has a UNIQUE constraint; Drive `display_path` must be unique per doc — use the folder-relative path which is unique. If a collision is possible, the plan's `GoogleDriveSource` disambiguates by appending the file id; see Task 4.)

Add methods:

```python
    def doc_by_id(self, doc_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_docs WHERE doc_id = ?", (doc_id,)
            ).fetchone()
        return dict(row) if row else None

    def delete_missing(self, origin: str, seen_ids: set[str]) -> int:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT doc_id FROM knowledge_docs WHERE origin = ?", (origin,)
            ).fetchall()
            removed = 0
            for row in rows:
                if row["doc_id"] not in seen_ids:
                    connection.execute(
                        "DELETE FROM knowledge_chunks WHERE doc_id = ?", (row["doc_id"],)
                    )
                    connection.execute(
                        "DELETE FROM knowledge_docs WHERE doc_id = ?", (row["doc_id"],)
                    )
                    removed += 1
        return removed
```

Update `list_docs` + `stats` to accept an optional `origin` filter:

```python
    def list_docs(self, origin: str | None = None) -> list[dict]:
        query = "SELECT path, chunk_count, status, indexed_at, origin FROM knowledge_docs"
        params: tuple = ()
        if origin is not None:
            query += " WHERE origin = ?"
            params = (origin,)
        query += " ORDER BY path"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def stats(self, origin: str | None = None) -> dict:
        with self._connect() as connection:
            if origin is None:
                docs = connection.execute("SELECT COUNT(*) AS c FROM knowledge_docs").fetchone()["c"]
                chunks = connection.execute("SELECT COUNT(*) AS c FROM knowledge_chunks").fetchone()["c"]
            else:
                docs = connection.execute(
                    "SELECT COUNT(*) AS c FROM knowledge_docs WHERE origin = ?", (origin,)
                ).fetchone()["c"]
                chunks = connection.execute(
                    "SELECT COUNT(*) AS c FROM knowledge_chunks WHERE doc_id IN "
                    "(SELECT doc_id FROM knowledge_docs WHERE origin = ?)",
                    (origin,),
                ).fetchone()["c"]
        return {"doc_count": docs, "chunk_count": chunks}
```

Update the `base.py` protocol signatures to match.

- [ ] **Step 5: Run + verify pass**

Run: `python -m pytest services/assistant-core/tests/test_vector_store.py -q`
Expected: PASS (existing + 2 new). The existing tests call `upsert_doc(... , "mock")` positionally with `hash` as the 3rd arg — those now pass `version` in that slot (same string), and `origin` defaults to `local`; they still pass.

- [ ] **Step 6: Log + commit**

Write `logs/vector-store-origin-version_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/vector/store/ services/assistant-core/tests/test_vector_store.py logs/vector-store-origin-version_2026-07-25_log.md
git commit -m "feat: vector store origin/version columns + per-origin ops"
```

---

### Task 2: `KnowledgeSource` protocol + `LocalFolderSource` + source-based indexer

**Files:**
- Create: `services/assistant-core/src/violet_assistant/knowledge/sources/__init__.py`
- Create: `services/assistant-core/src/violet_assistant/knowledge/sources/base.py`
- Create: `services/assistant-core/src/violet_assistant/knowledge/sources/local_folder.py`
- Modify: `services/assistant-core/src/violet_assistant/knowledge/indexer.py`
- Modify: `services/assistant-core/src/violet_assistant/main.py` (build sources list)
- Test: `services/assistant-core/tests/test_indexer.py` (rewrite to source-based), `services/assistant-core/tests/test_sources.py`

**Interfaces:**
- Produces: `SourceDocument` dataclass; `KnowledgeSource` protocol; `LocalFolderSource(knowledge_dir)`; `KnowledgeIndexer(embedder, store, sources, chunk_size, chunk_overlap)` with `async reindex(full=False, only=None)`.

- [ ] **Step 1: Write failing tests**

```python
# services/assistant-core/tests/test_sources.py
from __future__ import annotations

from violet_assistant.knowledge.sources.local_folder import LocalFolderSource


def test_local_source_lists_and_reads(tmp_path):
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "skip.xyz").write_text("no", encoding="utf-8")
    source = LocalFolderSource(tmp_path)
    docs = list(source.list_documents())
    assert len(docs) == 1
    doc = docs[0]
    assert doc.doc_id == "local:a.txt"
    assert doc.filename == "a.txt"
    assert source.read(doc) == b"hello"
    assert source.status()["connected"] is True
```

```python
# rewrite services/assistant-core/tests/test_indexer.py to use sources
from __future__ import annotations

import pytest

from violet_assistant.knowledge.indexer import KnowledgeIndexer
from violet_assistant.knowledge.sources.local_folder import LocalFolderSource
from violet_assistant.vector.embeddings.mock_embedder import MockEmbedder
from violet_assistant.vector.store.sqlite_vector_store import SqliteVectorStore


def _indexer(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    store = SqliteVectorStore(tmp_path / "knowledge.db")
    store.initialize()
    indexer = KnowledgeIndexer(MockEmbedder(), store, [LocalFolderSource(kdir)])
    return indexer, kdir, store


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
async def test_reindex_records_error_for_unreadable_supported_file(tmp_path):
    indexer, kdir, store = _indexer(tmp_path)
    (kdir / "empty.txt").write_text("   ", encoding="utf-8")
    report = await indexer.reindex()
    assert report["indexed"] == 0
    assert len(report["errors"]) == 1


@pytest.mark.asyncio
async def test_reindex_only_one_origin_leaves_others(tmp_path):
    # a fake second source proves per-origin cleanup isolation
    indexer, kdir, store = _indexer(tmp_path)
    (kdir / "a.txt").write_text("hello", encoding="utf-8")
    await indexer.reindex()
    # inject an unrelated gdrive doc directly, then reindex only=local
    store.upsert_doc("gdrive:1", "Drive/x", "v1", 1.0, [("y", [1.0, 0.0])], "mock", origin="gdrive")
    report = await indexer.reindex(only="local")
    assert store.stats(origin="gdrive")["doc_count"] == 1  # untouched
    assert report["sources"]["local"]["skipped"] == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_sources.py services/assistant-core/tests/test_indexer.py -q`
Expected: FAIL (modules/signatures missing).

- [ ] **Step 3: Implement the source protocol + document**

```python
# knowledge/sources/__init__.py  (empty)
```

```python
# knowledge/sources/base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass(frozen=True)
class SourceDocument:
    doc_id: str        # namespaced + stable, e.g. "local:notes.md" / "gdrive:<id>"
    display_path: str   # unique human label
    version: str        # change token: content hash | md5Checksum | modifiedTime
    filename: str       # name with extension (drives extractor selection)
    mime: str = ""      # source mime (Drive export decisions)


class KnowledgeSource(Protocol):
    name: str  # also the `origin` stored per doc

    def status(self) -> dict: ...
    def list_documents(self) -> Iterable[SourceDocument]: ...
    def read(self, doc: SourceDocument) -> bytes: ...
```

- [ ] **Step 4: Implement `LocalFolderSource`**

```python
# knowledge/sources/local_folder.py
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from violet_assistant.knowledge.sources.base import SourceDocument

_SUPPORTED = {
    ".txt", ".md", ".markdown", ".log", ".rst",
    ".csv", ".tsv", ".xlsx", ".xlsm", ".pdf", ".docx", ".json",
}


class LocalFolderSource:
    name = "local"

    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = Path(knowledge_dir)

    def status(self) -> dict:
        exists = self.knowledge_dir.exists()
        return {
            "name": "local",
            "connected": exists,
            "detail": "ok" if exists else "folder_missing",
            "folder": str(self.knowledge_dir),
        }

    def list_documents(self) -> Iterable[SourceDocument]:
        if not self.knowledge_dir.exists():
            return
        for path in sorted(self.knowledge_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _SUPPORTED:
                continue
            rel = str(path.relative_to(self.knowledge_dir).as_posix())
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            yield SourceDocument(
                doc_id=f"local:{rel}",
                display_path=rel,
                version=digest,
                filename=path.name,
            )

    def read(self, doc: SourceDocument) -> bytes:
        rel = doc.doc_id.split("local:", 1)[1]
        return (self.knowledge_dir / rel).read_bytes()
```

- [ ] **Step 5: Rewrite the indexer to iterate sources**

```python
# knowledge/indexer.py
from __future__ import annotations

from violet_assistant.ingestion.extractors import ExtractionError, extract_text
from violet_assistant.vector.chunker import chunk_text


class KnowledgeIndexer:
    def __init__(self, embedder, store, sources, chunk_size=1000, chunk_overlap=150):
        self.embedder = embedder
        self.store = store
        self.sources = list(sources)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def reindex(self, full: bool = False, only: str | None = None) -> dict:
        report = {
            "indexed": 0, "skipped": 0, "removed": 0, "chunks": 0,
            "errors": [], "sources": {},
        }
        for source in self.sources:
            if only is not None and source.name != only:
                continue
            per = {"indexed": 0, "skipped": 0, "removed": 0, "chunks": 0, "errors": []}
            seen: set[str] = set()
            try:
                documents = list(source.list_documents())
            except Exception as exc:  # noqa: BLE001 — a dead source must not kill others
                per["errors"].append({"path": source.name, "error": str(exc)})
                report["sources"][source.name] = per
                continue
            for doc in documents:
                seen.add(doc.doc_id)
                existing = self.store.doc_by_id(doc.doc_id)
                if not full and existing and existing["version"] == doc.version:
                    per["skipped"] += 1
                    continue
                try:
                    data = source.read(doc)
                    extracted = extract_text(doc.filename, data, max_chars=None)
                    pieces = chunk_text(extracted["text"], self.chunk_size, self.chunk_overlap)
                    if not pieces:
                        raise ExtractionError("no chunks produced")
                    vectors = await self.embedder.embed(pieces)
                    self.store.upsert_doc(
                        doc_id=doc.doc_id,
                        path=doc.display_path,
                        version=doc.version,
                        mtime=0.0,
                        chunks=list(zip(pieces, vectors)),
                        model=self.embedder.name,
                        origin=source.name,
                    )
                    per["indexed"] += 1
                    per["chunks"] += len(pieces)
                except Exception as exc:  # noqa: BLE001
                    per["errors"].append({"path": doc.display_path, "error": str(exc)})
            per["removed"] = self.store.delete_missing(source.name, seen)
            report["sources"][source.name] = per
            for key in ("indexed", "skipped", "removed", "chunks"):
                report[key] += per[key]
            report["errors"].extend(per["errors"])
        return report
```

- [ ] **Step 6: Update `main.py` to build a sources list**

Replace the knowledge-indexer construction so it builds sources from `KNOWLEDGE_SOURCES`:

```python
    knowledge_indexer = None
    knowledge_store = None
    knowledge_model = "none"
    knowledge_sources = []
    if active_settings.rag_provider.strip().lower() == "vector":
        from violet_assistant.knowledge.sources.local_folder import LocalFolderSource

        knowledge_store = SqliteVectorStore(active_settings.knowledge_db)
        knowledge_store.initialize()
        knowledge_embedder = create_embedder(active_settings)
        knowledge_model = knowledge_embedder.name
        enabled = {s.strip() for s in active_settings.knowledge_sources.split(",") if s.strip()}
        if "local" in enabled:
            knowledge_sources.append(LocalFolderSource(active_settings.knowledge_dir))
        # gdrive source appended in Task 5
        knowledge_indexer = KnowledgeIndexer(
            embedder=knowledge_embedder,
            store=knowledge_store,
            sources=knowledge_sources,
            chunk_size=active_settings.knowledge_chunk_size,
            chunk_overlap=active_settings.knowledge_chunk_overlap,
        )
        if active_settings.knowledge_scan_on_startup:
            import asyncio
            try:
                asyncio.new_event_loop().run_until_complete(knowledge_indexer.reindex())
            except Exception:  # noqa: BLE001
                pass
```

Add `knowledge_sources: str = "local"` to `Settings` and
`knowledge_sources=os.getenv("KNOWLEDGE_SOURCES", "local")` to `load_settings`
(full env table is added in Task 5; add just this one now so main.py imports).

- [ ] **Step 7: Run + verify pass**

Run: `python -m pytest services/assistant-core/tests/test_sources.py services/assistant-core/tests/test_indexer.py -q`
Expected: PASS. Then full suite `python -m pytest -q` (the knowledge-routes test still constructs `KnowledgeIndexer(MockEmbedder(), store, kdir)` positionally — update that test to pass `[LocalFolderSource(kdir)]`).

- [ ] **Step 8: Fix the knowledge-routes test constructor**

In `tests/test_knowledge_routes.py`, change `KnowledgeIndexer(MockEmbedder(), store, kdir)` to:

```python
    from violet_assistant.knowledge.sources.local_folder import LocalFolderSource
    indexer = KnowledgeIndexer(MockEmbedder(), store, [LocalFolderSource(kdir)])
```

Run `python -m pytest -q` → all PASS.

- [ ] **Step 9: Log + commit**

Write `logs/knowledge-source-abstraction_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/knowledge/ services/assistant-core/src/violet_assistant/main.py services/assistant-core/src/violet_assistant/config.py services/assistant-core/tests/test_sources.py services/assistant-core/tests/test_indexer.py services/assistant-core/tests/test_knowledge_routes.py logs/knowledge-source-abstraction_2026-07-25_log.md
git commit -m "refactor: source-abstraction indexer + LocalFolderSource"
```

---

### Task 3: Google OAuth helper

**Files:**
- Create: `services/assistant-core/src/violet_assistant/knowledge/gdrive_auth.py`
- Test: `services/assistant-core/tests/test_gdrive_auth.py`

**Interfaces:**
- Produces: `token_path(settings) -> Path`; `is_authorized(settings) -> bool`; `load_credentials(settings)` (lazy-imports google libs; returns creds or None); `authorize(settings)` (interactive, not unit-tested); `revoke(settings) -> bool`.

- [ ] **Step 1: Write failing tests (lib-free paths only)**

```python
# services/assistant-core/tests/test_gdrive_auth.py
from __future__ import annotations

from violet_assistant.config import load_settings
from violet_assistant.knowledge import gdrive_auth


def _settings(tmp_path, **env):
    import os
    for k, v in env.items():
        os.environ[k] = v
    try:
        return load_settings(tmp_path)
    finally:
        for k in env:
            os.environ.pop(k, None)


def test_not_authorized_when_no_token(tmp_path):
    settings = load_settings(tmp_path)
    assert gdrive_auth.is_authorized(settings) is False
    assert gdrive_auth.load_credentials(settings) is None


def test_revoke_deletes_token_file(tmp_path):
    settings = load_settings(tmp_path)
    path = gdrive_auth.token_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    assert gdrive_auth.is_authorized(settings) is True
    assert gdrive_auth.revoke(settings) is True
    assert gdrive_auth.is_authorized(settings) is False
    assert gdrive_auth.revoke(settings) is False  # already gone
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_gdrive_auth.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement (lazy imports inside functions)**

```python
# knowledge/gdrive_auth.py
from __future__ import annotations

from pathlib import Path

from violet_assistant.config import Settings

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def token_path(settings: Settings) -> Path:
    return Path(settings.gdrive_token_path)


def is_authorized(settings: Settings) -> bool:
    return token_path(settings).exists()


def load_credentials(settings: Settings):
    """Return valid google Credentials (refreshing if needed) or None.

    Returns None without importing google libs when no token file exists yet.
    """
    path = token_path(settings)
    if not path.exists():
        return None
    from google.oauth2.credentials import Credentials  # lazy
    from google.auth.transport.requests import Request  # lazy

    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json(), encoding="utf-8")
    return creds if creds and creds.valid else None


def authorize(settings: Settings):
    """Interactive one-time consent (opens the local browser). Not unit-tested."""
    if not settings.google_oauth_client_secrets:
        raise ValueError("GOOGLE_OAUTH_CLIENT_SECRETS is not set.")
    from google_auth_oauthlib.flow import InstalledAppFlow  # lazy

    flow = InstalledAppFlow.from_client_secrets_file(
        settings.google_oauth_client_secrets, SCOPES
    )
    creds = flow.run_local_server(port=0)
    path = token_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def revoke(settings: Settings) -> bool:
    path = token_path(settings)
    if path.exists():
        path.unlink()
        return True
    return False


if __name__ == "__main__":  # CLI fallback: python -m violet_assistant.knowledge.gdrive_auth
    from violet_assistant.config import load_settings

    authorize(load_settings())
    print("Google Drive authorized.")
```

Add `gdrive_token_path` + `google_oauth_client_secrets` to `Settings` now (full env table in Task 5):

```python
    gdrive_token_path: str = ""      # default filled in load_settings
    google_oauth_client_secrets: str = ""
```

and in `load_settings`:

```python
        gdrive_token_path=os.getenv("GDRIVE_TOKEN_PATH", str(root / "data" / "gdrive_token.json")),
        google_oauth_client_secrets=os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS", ""),
```

- [ ] **Step 4: Run + verify pass**

Run: `python -m pytest services/assistant-core/tests/test_gdrive_auth.py -q`
Expected: PASS (2 tests, no google libs needed).

- [ ] **Step 5: Log + commit**

Write `logs/gdrive-oauth_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/knowledge/gdrive_auth.py services/assistant-core/src/violet_assistant/config.py services/assistant-core/tests/test_gdrive_auth.py logs/gdrive-oauth_2026-07-25_log.md
git commit -m "feat: google drive OAuth helper (installed-app flow)"
```

---

### Task 4: `GoogleDriveSource`

**Files:**
- Create: `services/assistant-core/src/violet_assistant/knowledge/sources/google_drive.py`
- Test: `services/assistant-core/tests/test_gdrive_source.py`

**Interfaces:**
- Produces: `GoogleDriveSource(settings, service=None)` implementing `KnowledgeSource` (`name="gdrive"`); the `service` param is an injected Drive client for tests. Handles Shared Drives, recursion, native export vs binary download, mime→extension mapping.

- [ ] **Step 1: Write failing tests with an injected fake Drive client**

```python
# services/assistant-core/tests/test_gdrive_source.py
from __future__ import annotations

from violet_assistant.config import load_settings
from violet_assistant.knowledge.sources.google_drive import GoogleDriveSource


class _FakeFiles:
    def __init__(self, tree, exports, media):
        self._tree = tree      # parent_id -> list[file dicts]
        self._exports = exports  # file_id -> bytes
        self._media = media    # file_id -> bytes
        self.list_kwargs = []

    def list(self, **kwargs):
        self.list_kwargs.append(kwargs)
        # parse the parent id out of the q string
        q = kwargs["q"]
        parent = q.split("'")[1]
        files = self._tree.get(parent, [])
        return _Exec({"files": files, "nextPageToken": None})

    def export_media(self, fileId, mimeType):
        return _Exec(self._exports[fileId])

    def get_media(self, fileId, supportsAllDrives=True):
        return _Exec(self._media[fileId])


class _Exec:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class _FakeService:
    def __init__(self, files):
        self._files = files

    def files(self):
        return self._files


def _source(tmp_path, tree, exports, media, folder="root", shared=""):
    import os
    os.environ["GDRIVE_FOLDER_ID"] = folder
    os.environ["GDRIVE_SHARED_DRIVE_ID"] = shared
    os.environ["GOOGLE_OAUTH_CLIENT_SECRETS"] = "dummy.json"
    try:
        settings = load_settings(tmp_path)
    finally:
        for k in ("GDRIVE_FOLDER_ID", "GDRIVE_SHARED_DRIVE_ID", "GOOGLE_OAUTH_CLIENT_SECRETS"):
            os.environ.pop(k, None)
    service = _FakeService(_FakeFiles(tree, exports, media))
    return GoogleDriveSource(settings, service=service)


def test_lists_recursively_and_reads_binary_and_native(tmp_path):
    tree = {
        "root": [
            {"id": "f1", "name": "report.pdf", "mimeType": "application/pdf",
             "md5Checksum": "abc", "modifiedTime": "t1"},
            {"id": "sub", "name": "Sub", "mimeType": "application/vnd.google-apps.folder",
             "modifiedTime": "t0"},
        ],
        "sub": [
            {"id": "d1", "name": "Notes", "mimeType": "application/vnd.google-apps.document",
             "modifiedTime": "t2"},
        ],
    }
    exports = {"d1": b"# Notes\nbody"}
    media = {"f1": b"%PDF-1.4 ..."}
    source = _source(tmp_path, tree, exports, media)

    docs = {d.doc_id: d for d in source.list_documents()}
    assert set(docs) == {"gdrive:f1", "gdrive:d1"}
    assert docs["gdrive:f1"].filename == "report.pdf"
    assert docs["gdrive:f1"].version == "abc"          # md5 preferred
    assert docs["gdrive:d1"].filename == "Notes.md"    # exported doc gets .md
    assert docs["gdrive:d1"].version == "t2"           # native → modifiedTime

    assert source.read(docs["gdrive:f1"]) == b"%PDF-1.4 ..."
    assert source.read(docs["gdrive:d1"]) == b"# Notes\nbody"


def test_shared_drive_params_passed(tmp_path):
    tree = {"root": []}
    source = _source(tmp_path, tree, {}, {}, folder="root", shared="SD1")
    list(source.list_documents())
    kwargs = source._service.files().list_kwargs[0]
    assert kwargs["supportsAllDrives"] is True
    assert kwargs["includeItemsFromAllDrives"] is True
    assert kwargs["corpora"] == "drive"
    assert kwargs["driveId"] == "SD1"


def test_status_needs_config(tmp_path):
    settings = load_settings(tmp_path)  # nothing configured
    source = GoogleDriveSource(settings, service=None)
    st = source.status()
    assert st["name"] == "gdrive"
    assert st["connected"] is False
    assert st["detail"] in {"not_configured", "needs_auth"}
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_gdrive_source.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `GoogleDriveSource`**

```python
# knowledge/sources/google_drive.py
from __future__ import annotations

from typing import Iterable

from violet_assistant.config import Settings
from violet_assistant.knowledge.sources.base import SourceDocument

_FOLDER_MIME = "application/vnd.google-apps.folder"

# native google mime -> (export mime, extension)
_EXPORT = {
    "application/vnd.google-apps.document": ("text/markdown", "md"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", "csv"),
    "application/vnd.google-apps.presentation": ("text/plain", "txt"),
}
# binary mimes we can extract (by resulting extension)
_BINARY_EXT = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/csv": "csv",
    "application/json": "json",
}


class GoogleDriveSource:
    name = "gdrive"

    def __init__(self, settings: Settings, service=None) -> None:
        self.settings = settings
        self._service = service  # injected in tests; built lazily otherwise
        # remember export decisions so read() mirrors list_documents()
        self._doc_meta: dict[str, dict] = {}

    # -- service / status -------------------------------------------------
    def _get_service(self):
        if self._service is not None:
            return self._service
        from violet_assistant.knowledge import gdrive_auth
        creds = gdrive_auth.load_credentials(self.settings)
        if creds is None:
            return None
        from googleapiclient.discovery import build  # lazy
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def status(self) -> dict:
        if not (self.settings.gdrive_folder_id and self.settings.google_oauth_client_secrets):
            return {"name": "gdrive", "connected": False, "detail": "not_configured"}
        try:
            service = self._get_service()
        except Exception as exc:  # noqa: BLE001 — missing libs etc.
            return {"name": "gdrive", "connected": False, "detail": str(exc)}
        if service is None:
            return {"name": "gdrive", "connected": False, "detail": "needs_auth",
                    "folder_id": self.settings.gdrive_folder_id}
        return {"name": "gdrive", "connected": True, "detail": "connected",
                "folder_id": self.settings.gdrive_folder_id}

    # -- listing ----------------------------------------------------------
    def _list_kwargs(self, parent_id: str, page_token: str | None) -> dict:
        kwargs = {
            "q": f"'{parent_id}' in parents and trashed = false",
            "fields": "nextPageToken, files(id, name, mimeType, md5Checksum, modifiedTime)",
            "pageSize": 200,
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
            "pageToken": page_token,
        }
        if self.settings.gdrive_shared_drive_id:
            kwargs["corpora"] = "drive"
            kwargs["driveId"] = self.settings.gdrive_shared_drive_id
        else:
            kwargs["corpora"] = "allDrives"
        return kwargs

    def _children(self, service, parent_id: str) -> list[dict]:
        out: list[dict] = []
        page_token = None
        while True:
            resp = service.files().list(**self._list_kwargs(parent_id, page_token)).execute()
            out.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return out

    def list_documents(self) -> Iterable[SourceDocument]:
        service = self._get_service()
        if service is None:
            return
        stack = [(self.settings.gdrive_folder_id, "")]
        while stack:
            parent, prefix = stack.pop()
            for f in self._children(service, parent):
                mime = f["mimeType"]
                name = f["name"]
                rel = f"{prefix}{name}" if not prefix else f"{prefix}/{name}"
                if mime == _FOLDER_MIME:
                    stack.append((f["id"], rel))
                    continue
                mapped = self._map(f)
                if mapped is None:
                    continue
                filename, export_mime, version = mapped
                self._doc_meta[f["id"]] = {"export_mime": export_mime}
                yield SourceDocument(
                    doc_id=f"gdrive:{f['id']}",
                    display_path=f"{rel}#{f['id'][:6]}",  # id suffix keeps path UNIQUE
                    version=version,
                    filename=filename,
                    mime=mime,
                )

    def _map(self, f: dict):
        """Return (filename, export_mime_or_None, version) or None if unsupported."""
        mime, name = f["mimeType"], f["name"]
        if mime in _EXPORT:
            export_mime, ext = _EXPORT[mime]
            filename = name if name.lower().endswith("." + ext) else f"{name}.{ext}"
            version = f.get("md5Checksum") or f.get("modifiedTime") or ""
            return filename, export_mime, version
        if mime in _BINARY_EXT:
            ext = _BINARY_EXT[mime]
            filename = name if name.lower().endswith("." + ext) else f"{name}.{ext}"
            version = f.get("md5Checksum") or f.get("modifiedTime") or ""
            return filename, None, version
        return None

    # -- read -------------------------------------------------------------
    def read(self, doc: SourceDocument) -> bytes:
        service = self._get_service()
        if service is None:
            raise RuntimeError("Google Drive is not authorized.")
        file_id = doc.doc_id.split("gdrive:", 1)[1]
        meta = self._doc_meta.get(file_id, {})
        export_mime = meta.get("export_mime")
        if export_mime:
            return service.files().export_media(fileId=file_id, mimeType=export_mime).execute()
        return service.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
```

Note on `read()` after a restart: `_doc_meta` is populated by `list_documents()`, which the indexer always calls before `read()` in the same run — so export decisions are always present. (No cross-process state needed.)

- [ ] **Step 4: Run + verify pass**

Run: `python -m pytest services/assistant-core/tests/test_gdrive_source.py -q`
Expected: PASS (3 tests).

Note: the fake `get_media` in the test accepts `supportsAllDrives` — the real client does too.

- [ ] **Step 5: Log + commit**

Write `logs/gdrive-source_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/knowledge/sources/google_drive.py services/assistant-core/tests/test_gdrive_source.py logs/gdrive-source_2026-07-25_log.md
git commit -m "feat: GoogleDriveSource (recursive, shared drive, export/download)"
```

---

### Task 5: Config, dependency extra, and main wiring

**Files:**
- Modify: `services/assistant-core/src/violet_assistant/config.py` (remaining gdrive fields)
- Modify: `services/assistant-core/src/violet_assistant/main.py` (append gdrive source)
- Modify: `pyproject.toml` (add `drive` optional extra)
- Modify: `.env.example` (document new vars, names only)
- Test: `services/assistant-core/tests/test_config_gdrive.py`

**Interfaces:**
- Produces: `Settings.gdrive_folder_id`, `gdrive_shared_drive_id`, `gdrive_export_doc` (plus the ones from Tasks 2–3); `GoogleDriveSource` appended to the source list when enabled.

- [ ] **Step 1: Write failing config test**

```python
# services/assistant-core/tests/test_config_gdrive.py
from __future__ import annotations

import os

from violet_assistant.config import load_settings


def test_gdrive_settings_read_from_env(tmp_path):
    for k, v in {
        "KNOWLEDGE_SOURCES": "local,gdrive",
        "GDRIVE_FOLDER_ID": "FID",
        "GDRIVE_SHARED_DRIVE_ID": "SD1",
    }.items():
        os.environ[k] = v
    try:
        s = load_settings(tmp_path)
        assert s.knowledge_sources == "local,gdrive"
        assert s.gdrive_folder_id == "FID"
        assert s.gdrive_shared_drive_id == "SD1"
        # token path defaults under the repo data dir
        assert s.gdrive_token_path.endswith("gdrive_token.json")
    finally:
        for k in ("KNOWLEDGE_SOURCES", "GDRIVE_FOLDER_ID", "GDRIVE_SHARED_DRIVE_ID"):
            os.environ.pop(k, None)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_config_gdrive.py -q`
Expected: FAIL (fields missing).

- [ ] **Step 3: Add remaining Settings fields**

Add to the dataclass (some added in Tasks 2–3; ensure all present):

```python
    knowledge_sources: str = "local"
    gdrive_folder_id: str = ""
    gdrive_shared_drive_id: str = ""
    gdrive_token_path: str = ""
    google_oauth_client_secrets: str = ""
    gdrive_export_doc: str = "text/markdown"
```

Add to `load_settings`:

```python
        knowledge_sources=os.getenv("KNOWLEDGE_SOURCES", "local"),
        gdrive_folder_id=os.getenv("GDRIVE_FOLDER_ID", ""),
        gdrive_shared_drive_id=os.getenv("GDRIVE_SHARED_DRIVE_ID", ""),
        gdrive_token_path=os.getenv("GDRIVE_TOKEN_PATH", str(root / "data" / "gdrive_token.json")),
        google_oauth_client_secrets=os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS", ""),
        gdrive_export_doc=os.getenv("GDRIVE_EXPORT_DOC", "text/markdown"),
```

- [ ] **Step 4: Append the gdrive source in main.py**

Where Task 2 left `# gdrive source appended in Task 5`:

```python
        if "gdrive" in enabled and active_settings.gdrive_folder_id and active_settings.google_oauth_client_secrets:
            from violet_assistant.knowledge.sources.google_drive import GoogleDriveSource
            knowledge_sources.append(GoogleDriveSource(active_settings))
```

Keep a module-level reference so routes can reach it (Task 6): store on a small holder, e.g. set `knowledge_gdrive = knowledge_sources[-1] if appended else None` and pass into the knowledge router.

- [ ] **Step 5: Add the `drive` optional extra + document env**

In `pyproject.toml` `[project.optional-dependencies]`:

```toml
drive = [
  "google-api-python-client>=2.100",
  "google-auth>=2.30",
  "google-auth-oauthlib>=1.2",
]
```

Append to `.env.example` (names only, no secrets):

```
# Knowledge base — Google Drive (Phase C). Requires: pip install -e ".[drive]"
KNOWLEDGE_SOURCES=local
GDRIVE_FOLDER_ID=
GDRIVE_SHARED_DRIVE_ID=
GOOGLE_OAUTH_CLIENT_SECRETS=
GDRIVE_TOKEN_PATH=
GDRIVE_EXPORT_DOC=text/markdown
```

- [ ] **Step 6: Run + verify pass**

Run: `python -m pytest services/assistant-core/tests/test_config_gdrive.py -q` → PASS.
Run full: `python -m pytest -q` → PASS.
App boot: `PYTHONPATH=services/assistant-core/src python -c "from violet_assistant.main import create_app; from violet_assistant.config import load_settings; import pathlib; create_app(load_settings(pathlib.Path('.').resolve()))"` → no error (Drive off by default; google libs not imported).

- [ ] **Step 7: Log + commit**

Write `logs/gdrive-config-wiring_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/config.py services/assistant-core/src/violet_assistant/main.py pyproject.toml .env.example services/assistant-core/tests/test_config_gdrive.py logs/gdrive-config-wiring_2026-07-25_log.md
git commit -m "feat: gdrive config + optional drive extra + source wiring"
```

---

### Task 6: Knowledge routes — per-source status + gdrive connect/status/disconnect

**Files:**
- Modify: `services/assistant-core/src/violet_assistant/routes/knowledge.py`
- Modify: `services/assistant-core/src/violet_assistant/main.py` (pass sources + gdrive source + settings to router)
- Test: `services/assistant-core/tests/test_knowledge_routes.py` (extend)

**Interfaces:**
- Produces: `GET /api/knowledge` now returns `sources: [status...]`; `reindex` accepts `source`; `POST /api/knowledge/gdrive/connect`, `GET /api/knowledge/gdrive/status`, `POST /api/knowledge/gdrive/disconnect`.

- [ ] **Step 1: Write failing tests**

```python
# extend services/assistant-core/tests/test_knowledge_routes.py
@pytest.mark.asyncio
async def test_status_includes_sources(tmp_path):
    kdir = tmp_path / "knowledge"; kdir.mkdir()
    from violet_assistant.knowledge.sources.local_folder import LocalFolderSource
    from violet_assistant.config import load_settings
    store = SqliteVectorStore(tmp_path / "k.db"); store.initialize()
    src = LocalFolderSource(kdir)
    indexer = KnowledgeIndexer(MockEmbedder(), store, [src])
    router = create_knowledge_router(indexer, store, str(kdir), "mock", [src], None, load_settings(tmp_path))
    body = await _endpoint(router, "GET")()
    assert any(s["name"] == "local" for s in body["sources"])


@pytest.mark.asyncio
async def test_reindex_source_filter(tmp_path):
    kdir = tmp_path / "knowledge"; kdir.mkdir()
    (kdir / "a.txt").write_text("hi", encoding="utf-8")
    from violet_assistant.knowledge.sources.local_folder import LocalFolderSource
    from violet_assistant.config import load_settings
    store = SqliteVectorStore(tmp_path / "k.db"); store.initialize()
    src = LocalFolderSource(kdir)
    indexer = KnowledgeIndexer(MockEmbedder(), store, [src])
    router = create_knowledge_router(indexer, store, str(kdir), "mock", [src], None, load_settings(tmp_path))
    report = await _endpoint(router, "POST")(ReindexRequest(full=False, source="local"))
    assert report["sources"]["local"]["indexed"] == 1
```

(Add `source: str | None = None` to `ReindexRequest`.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_knowledge_routes.py -q`
Expected: FAIL (signature mismatch / new fields).

- [ ] **Step 3: Rewrite the knowledge router**

```python
# routes/knowledge.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class ReindexRequest(BaseModel):
    full: bool = False
    source: str | None = None


def create_knowledge_router(
    indexer, store, knowledge_dir, model, sources=None, gdrive_source=None, settings=None
):
    # Defaults keep the Phase A 4-arg call sites (and their tests) working unchanged.
    router = APIRouter()

    @router.get("/api/knowledge")
    async def status() -> dict:
        stats = store.stats() if store else {"doc_count": 0, "chunk_count": 0}
        return {
            "dir": str(knowledge_dir),
            "provider": model,
            "enabled": indexer is not None,
            "doc_count": stats["doc_count"],
            "chunk_count": stats["chunk_count"],
            "docs": store.list_docs() if store else [],
            "sources": [s.status() for s in (sources or [])],
        }

    @router.post("/api/knowledge/reindex")
    async def reindex(body: ReindexRequest) -> dict:
        if indexer is None:
            raise HTTPException(status_code=409, detail="Knowledge base is not enabled (set RAG_PROVIDER=vector).")
        return await indexer.reindex(full=body.full, only=body.source)

    @router.get("/api/knowledge/gdrive/status")
    async def gdrive_status() -> dict:
        if gdrive_source is None:
            return {"name": "gdrive", "connected": False, "detail": "not_configured"}
        return gdrive_source.status()

    @router.post("/api/knowledge/gdrive/connect")
    async def gdrive_connect() -> dict:
        if gdrive_source is None or settings is None:
            raise HTTPException(status_code=400, detail="Google Drive is not configured.")
        from violet_assistant.knowledge import gdrive_auth
        try:
            gdrive_auth.authorize(settings)  # opens local browser (one-time)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return gdrive_source.status()

    @router.post("/api/knowledge/gdrive/disconnect")
    async def gdrive_disconnect() -> dict:
        if settings is not None:
            from violet_assistant.knowledge import gdrive_auth
            gdrive_auth.revoke(settings)
        return {"name": "gdrive", "connected": False, "detail": "not_configured"}

    return router
```

- [ ] **Step 4: Update `main.py` router construction**

Track the gdrive source and pass everything:

```python
    knowledge_gdrive = next((s for s in knowledge_sources if s.name == "gdrive"), None)
    ...
    app.include_router(
        create_knowledge_router(
            knowledge_indexer,
            knowledge_store,
            str(active_settings.knowledge_dir),
            knowledge_model,
            knowledge_sources,
            knowledge_gdrive,
            active_settings,
        )
    )
```

- [ ] **Step 5: Run + verify pass**

Run: `python -m pytest services/assistant-core/tests/test_knowledge_routes.py -q` → PASS.
Full suite `python -m pytest -q` → PASS. App boot exposes `/api/knowledge/gdrive/status`.

- [ ] **Step 6: Log + commit**

Write `logs/gdrive-routes_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/routes/knowledge.py services/assistant-core/src/violet_assistant/main.py services/assistant-core/tests/test_knowledge_routes.py logs/gdrive-routes_2026-07-25_log.md
git commit -m "feat: knowledge routes for per-source status + gdrive connect"
```

---

### Task 7: Frontend — Sources UI + Drive connect

**Files:**
- Modify: `apps/web-client/src/lib/api.ts` (extend `KnowledgeInfo` with `sources`; add gdrive helpers; `source` arg to reindex)
- Modify: `apps/web-client/src/components/SettingsModal.tsx` (Sources block in the Knowledge section)
- Modify: `apps/web-client/src/App.tsx` (handlers pass through; refresh after connect)
- Verify: `cd apps/web-client && npm run build`

**Interfaces:**
- Consumes: `GET /api/knowledge` (`sources`), `gdrive/connect|status|disconnect`, `reindex {source}`.

- [ ] **Step 1: Extend `lib/api.ts`**

```typescript
export type SourceStatus = {
  name: string;
  connected: boolean;
  detail: string;
  folder?: string;
  folder_id?: string;
};

// add to KnowledgeInfo:
//   sources: SourceStatus[];

export async function reindexKnowledge(full = false, source?: string): Promise<ReindexReport> {
  return requestJson<ReindexReport>("/api/knowledge/reindex", {
    method: "POST",
    body: JSON.stringify({ full, source: source ?? null }),
  });
}

export async function connectGDrive(): Promise<SourceStatus> {
  return requestJson<SourceStatus>("/api/knowledge/gdrive/connect", { method: "POST" });
}

export async function disconnectGDrive(): Promise<SourceStatus> {
  return requestJson<SourceStatus>("/api/knowledge/gdrive/disconnect", { method: "POST" });
}
```

Add `sources: SourceStatus[]` to the `KnowledgeInfo` type (default `[]` tolerated by optional chaining in the UI).

- [ ] **Step 2: App handlers**

In `App.tsx`:
- `handleReindex(full: boolean, source?: string)` → `reindexKnowledge(full, source)` then `refreshKnowledge()`.
- `async function handleConnectGDrive() { setStatus({tone:"busy",text:"Opening Google consent…"}); try { await connectGDrive(); await refreshKnowledge(); setStatus({tone:"ok",text:"Google Drive connected"}); } catch(e){ setStatus({tone:"error",text: e instanceof Error ? e.message : "Connect failed"}); } }`
- `async function handleDisconnectGDrive() { await disconnectGDrive(); await refreshKnowledge(); }`
- Pass `onConnectGDrive`, `onDisconnectGDrive` to `SettingsModal` (and keep `onReindex` now `(full, source?)`).
- Import `connectGDrive`, `disconnectGDrive` from `./lib/api`.

- [ ] **Step 3: SettingsModal Sources block**

Extend `SettingsModalProps`: `onConnectGDrive: () => void`, `onDisconnectGDrive: () => void`, and change `onReindex` to `(full: boolean, source?: string) => void`.

Inside the Knowledge section, after the aggregate counts, render a per-source list from `knowledge.sources`:

```tsx
{knowledge.sources?.map((s) => (
  <div key={s.name} className="flex items-center gap-2 text-[11px] border-t border-navy-700/10 pt-2">
    <span className="font-medium capitalize text-steel-dark">{s.name}</span>
    <span className={s.connected ? "text-emerald-600" : "text-amber-600"}>
      {s.connected ? "connected" : s.detail}
    </span>
    {s.name === "gdrive" && !s.connected && s.detail !== "not_configured" && (
      <button onClick={onConnectGDrive} className="ml-auto text-steel-highlight hover:underline">
        Connect
      </button>
    )}
    {s.name === "gdrive" && s.connected && (
      <>
        <button onClick={() => onReindex(false, "gdrive")} className="ml-auto text-steel-highlight hover:underline">
          Sync
        </button>
        {devMode && (
          <button onClick={onDisconnectGDrive} className="text-steel/60 hover:underline">
            Disconnect
          </button>
        )}
      </>
    )}
  </div>
))}
```

When `gdrive` status `detail === "not_configured"`, show a hint (developer mode): "Set GDRIVE_FOLDER_ID + GOOGLE_OAUTH_CLIENT_SECRETS and install .[drive]." Keep the existing Reindex button as "Reindex all".

- [ ] **Step 4: Build**

Run: `cd apps/web-client && npm run build` → clean.

- [ ] **Step 5: Log + commit**

Write `logs/gdrive-frontend_2026-07-25_log.md`, then:

```bash
git add apps/web-client/src/lib/api.ts apps/web-client/src/components/SettingsModal.tsx apps/web-client/src/App.tsx logs/gdrive-frontend_2026-07-25_log.md
git commit -m "feat: knowledge sources UI + Google Drive connect"
```

---

## Final verification (after Task 7)
- `python -m pytest -q` → all PASS (no test imports google libs).
- App boot exposes `/api/knowledge`, `/api/knowledge/gdrive/status|connect|disconnect`; Drive off by default.
- `cd apps/web-client && npm run build` → clean.
- Manual (optional, needs real OAuth client + `pip install -e ".[drive]"`): set `KNOWLEDGE_SOURCES=local,gdrive`, `GDRIVE_FOLDER_ID`, `GOOGLE_OAUTH_CLIENT_SECRETS`; **Connect Google Drive** in Settings → consent → **Sync** → ask a question → answer cites a Drive file.

## Notes for the implementer
- No test may import `googleapiclient`/`google.*` — inject `service` into `GoogleDriveSource` and exercise only the lib-free paths of `gdrive_auth`.
- The `path` column is UNIQUE; Drive `display_path` appends a short file-id suffix to guarantee uniqueness across same-named files in different folders.
- `_doc_meta` in `GoogleDriveSource` is populated by `list_documents()`, always called before `read()` within a single `reindex` run — no persistence needed.
- Keep `origin`/`version` migration idempotent (guarded by PRAGMA), so repeated boots on an existing `knowledge.db` are safe.
