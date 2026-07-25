# Local Knowledge Base (RAG) + User/Developer UI Modes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Violet a local knowledge folder that auto-vectorizes into a retrievable knowledge base, and a persisted User/Developer mode that filters which controls the UI shows.

**Architecture:** New `vector/` (embeddings + SQLite vector store) and `knowledge/` (indexer) packages behind the existing `Retriever` seam; the orchestrator already injects retrieved `Chunk`s into the system prompt. A `ui_mode` preference extends the existing `PreferencesStore`. Embeddings default to a deterministic mock (zero setup) and switch to a local Ollama OpenAI-compatible endpoint via env. Vector search is pure-Python cosine over a dedicated `data/knowledge.db`.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, stdlib `sqlite3`/`urllib`/`array`/`hashlib` (no new deps), pytest; React 18 + TypeScript + Vite + Tailwind + lucide-react.

## Global Constraints

- Python `>=3.11`; backend package root `services/assistant-core/src/violet_assistant`.
- Run tests from repo root: `python -m pytest -q` (config in root `pyproject.toml`; basetemp `.tmp/pytest`). Async tests use `@pytest.mark.asyncio`.
- No new runtime dependencies — embeddings HTTP and vector math use stdlib.
- No secrets in code; secrets/infra stay in `.env`. Only UX/behavior prefs are runtime-editable.
- Test FastAPI routers by awaiting their endpoint callables directly (no `TestClient`/httpx — matches existing tests, e.g. `tests/test_preferences.py`).
- Embeddings default `EMBED_PROVIDER=mock` (deterministic, 256-dim) so everything runs with zero setup, mirroring `LLM_PROVIDER=mock`.
- Vectors persist to a dedicated SQLite file (`KNOWLEDGE_DB`, default `data/knowledge.db`), separate from the chat DB.
- SQLite idiom: `sqlite3.connect(path)`, `connection.row_factory = sqlite3.Row`, `with connection:` for write transactions.
- Changing `EMBED_MODEL` changes vector dimension → requires a full reindex.
- Every unit: tests where applicable + a `logs/{update}_{YYYY-MM-DD}_log.md` entry (template `logs/_TEMPLATE.md`) BEFORE committing. Date 2026-07-25.
- Frontend verified with `cd apps/web-client && npm run build`.

---

### Task 1: Embedding providers + factory

**Files:**
- Create: `services/assistant-core/src/violet_assistant/vector/__init__.py`
- Create: `services/assistant-core/src/violet_assistant/vector/embeddings/__init__.py`
- Create: `services/assistant-core/src/violet_assistant/vector/embeddings/base.py`
- Create: `services/assistant-core/src/violet_assistant/vector/embeddings/mock_embedder.py`
- Create: `services/assistant-core/src/violet_assistant/vector/embeddings/openai_compatible_embedder.py`
- Create: `services/assistant-core/src/violet_assistant/vector/embeddings/factory.py`
- Test: `services/assistant-core/tests/test_embeddings.py`

**Interfaces:**
- Produces: `EmbeddingProvider` protocol with `name: str` and `async embed(texts: list[str]) -> list[list[float]]`; `MockEmbedder(dim=256)`; `OpenAICompatibleEmbedder(base_url, model, api_key, timeout_seconds)`; `create_embedder(settings) -> EmbeddingProvider`.

- [ ] **Step 1: Write failing test**

```python
# services/assistant-core/tests/test_embeddings.py
from __future__ import annotations

import math

import pytest

from violet_assistant.vector.embeddings.mock_embedder import MockEmbedder


@pytest.mark.asyncio
async def test_mock_embedder_is_deterministic_and_normalized():
    emb = MockEmbedder(dim=256)
    a = (await emb.embed(["capital call notice"]))[0]
    b = (await emb.embed(["capital call notice"]))[0]
    assert a == b  # deterministic
    assert len(a) == 256
    norm = math.sqrt(sum(x * x for x in a))
    assert abs(norm - 1.0) < 1e-6  # L2-normalized


@pytest.mark.asyncio
async def test_mock_embedder_differs_for_different_text():
    emb = MockEmbedder(dim=256)
    a = (await emb.embed(["alpha"]))[0]
    b = (await emb.embed(["beta"]))[0]
    assert a != b
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_embeddings.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement base + mock**

```python
# vector/__init__.py  (empty)
# vector/embeddings/__init__.py  (empty)
```

```python
# vector/embeddings/base.py
from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    name: str

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text. All vectors share the same dimension."""
```

```python
# vector/embeddings/mock_embedder.py
from __future__ import annotations

import hashlib
import math
import re


class MockEmbedder:
    """Deterministic, offline embedder: hash tokens into a fixed-dim L2-normalized vector.

    Not semantically strong, but stable and dependency-free — enough to build and
    test the whole pipeline with no model server.
    """

    name = "mock"

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = re.findall(r"\w+", text.lower()) or [text]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]
```

- [ ] **Step 4: Run mock tests**

Run: `python -m pytest services/assistant-core/tests/test_embeddings.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Implement the HTTP embedder + factory**

```python
# vector/embeddings/openai_compatible_embedder.py
from __future__ import annotations

import asyncio
import json
from urllib import error, request


class OpenAICompatibleEmbedder:
    """POST {base_url}/embeddings — works with Ollama (/v1) and compatible servers."""

    name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed_sync, texts)

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self.model, "input": texts}
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = request.Request(
            f"{self.base_url}/embeddings", data=body, headers=headers, method="POST"
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Embeddings HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Embeddings unreachable: {exc.reason}") from exc
        items = sorted(data["data"], key=lambda d: d.get("index", 0))
        return [item["embedding"] for item in items]
```

```python
# vector/embeddings/factory.py
from __future__ import annotations

from violet_assistant.config import Settings
from violet_assistant.vector.embeddings.base import EmbeddingProvider
from violet_assistant.vector.embeddings.mock_embedder import MockEmbedder
from violet_assistant.vector.embeddings.openai_compatible_embedder import (
    OpenAICompatibleEmbedder,
)


def create_embedder(settings: Settings) -> EmbeddingProvider:
    provider = settings.embed_provider.strip().lower()
    if provider in {"mock", "none", ""}:
        return MockEmbedder()
    if provider in {"openai_compatible", "ollama", "openai"}:
        return OpenAICompatibleEmbedder(
            base_url=settings.embed_base_url,
            model=settings.embed_model,
            api_key=settings.embed_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    raise ValueError(f"Unsupported EMBED_PROVIDER={settings.embed_provider!r}")
```

- [ ] **Step 6: Add Settings fields (config.py)**

Add to the `Settings` dataclass (after web-search fields):

```python
    # Knowledge base / RAG (Phase A).
    knowledge_dir: Path | None = None
    knowledge_db: Path | None = None
    embed_provider: str = "mock"
    embed_base_url: str = "http://localhost:11434/v1"
    embed_model: str = "nomic-embed-text"
    embed_api_key: str | None = None
    knowledge_scan_on_startup: bool = True
    knowledge_chunk_size: int = 1000
    knowledge_chunk_overlap: int = 150
```

Add to `load_settings(...)`:

```python
        knowledge_dir=Path(os.getenv("KNOWLEDGE_DIR", str(root / "knowledge"))),
        knowledge_db=Path(os.getenv("KNOWLEDGE_DB", str(root / "data" / "knowledge.db"))),
        embed_provider=os.getenv("EMBED_PROVIDER", "mock").strip().lower(),
        embed_base_url=os.getenv("EMBED_BASE_URL", "http://localhost:11434/v1"),
        embed_model=os.getenv("EMBED_MODEL", "nomic-embed-text"),
        embed_api_key=os.getenv("EMBED_API_KEY") or None,
        knowledge_scan_on_startup=_env_bool("KNOWLEDGE_SCAN_ON_STARTUP", True),
        knowledge_chunk_size=int(os.getenv("KNOWLEDGE_CHUNK_SIZE", "1000")),
        knowledge_chunk_overlap=int(os.getenv("KNOWLEDGE_CHUNK_OVERLAP", "150")),
```

- [ ] **Step 7: Add a factory test**

```python
# append to tests/test_embeddings.py
from violet_assistant.config import load_settings
from violet_assistant.vector.embeddings.factory import create_embedder


def test_factory_defaults_to_mock(tmp_path):
    assert create_embedder(load_settings(tmp_path)).name == "mock"
```

- [ ] **Step 8: Run + log + commit**

Run: `python -m pytest services/assistant-core/tests/test_embeddings.py -q` → PASS.
Write `logs/embeddings-provider_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/vector services/assistant-core/src/violet_assistant/config.py services/assistant-core/tests/test_embeddings.py logs/embeddings-provider_2026-07-25_log.md
git commit -m "feat: embedding providers (mock + openai-compatible) + config"
```

---

### Task 2: Chunker

**Files:**
- Create: `services/assistant-core/src/violet_assistant/vector/chunker.py`
- Test: `services/assistant-core/tests/test_chunker.py`

**Interfaces:**
- Produces: `chunk_text(text: str, size: int = 1000, overlap: int = 150) -> list[str]`.

- [ ] **Step 1: Write failing test**

```python
# services/assistant-core/tests/test_chunker.py
from __future__ import annotations

from violet_assistant.vector.chunker import chunk_text


def test_short_text_is_one_chunk():
    assert chunk_text("hello world") == ["hello world"]


def test_empty_text_is_no_chunks():
    assert chunk_text("   ") == []


def test_long_text_splits_with_overlap():
    para = ("word " * 400).strip()  # ~2000 chars
    chunks = chunk_text(para, size=500, overlap=100)
    assert len(chunks) >= 4
    assert all(len(c) <= 700 for c in chunks)  # size + overlap slack
    # consecutive chunks share some tail/head text (overlap)
    assert chunks[0][-30:] in chunks[1] or chunks[1].startswith(chunks[0][-30:][:10])


def test_paragraph_boundaries_preferred():
    text = "Alpha para.\n\nBeta para.\n\nGamma para."
    chunks = chunk_text(text, size=12, overlap=0)
    assert "Alpha para." in chunks[0]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_chunker.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# vector/chunker.py
from __future__ import annotations

import re


def chunk_text(text: str, size: int = 1000, overlap: int = 150) -> list[str]:
    """Split text into ~size-char chunks on paragraph boundaries, with char overlap."""
    text = text.strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > size:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = (tail + "\n\n" + para).strip()
        else:
            current = (current + "\n\n" + para).strip() if current else para
        # a single oversized paragraph: hard-split it
        while len(current) > size:
            chunks.append(current[:size])
            current = (current[size - overlap :] if overlap else current[size:]).strip()
    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]
```

- [ ] **Step 4: Run + verify pass**

Run: `python -m pytest services/assistant-core/tests/test_chunker.py -q`
Expected: PASS.

- [ ] **Step 5: Log + commit**

Write `logs/chunker_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/vector/chunker.py services/assistant-core/tests/test_chunker.py logs/chunker_2026-07-25_log.md
git commit -m "feat: paragraph-aware text chunker"
```

---

### Task 3: SQLite vector store

**Files:**
- Create: `services/assistant-core/src/violet_assistant/vector/store/__init__.py`
- Create: `services/assistant-core/src/violet_assistant/vector/store/base.py`
- Create: `services/assistant-core/src/violet_assistant/vector/store/sqlite_vector_store.py`
- Test: `services/assistant-core/tests/test_vector_store.py`

**Interfaces:**
- Consumes: nothing external.
- Produces: `VectorStore` protocol; `SqliteVectorStore(db_path)` with `initialize()`, `doc_by_path(path) -> dict | None`, `upsert_doc(doc_id, path, hash, mtime, chunks: list[tuple[str, list[float]]], model)`, `query(vector, k, model) -> list[dict]` (each `{text, source, score, chunk_index}`), `delete_doc(doc_id)`, `list_docs() -> list[dict]`, `stats() -> dict`.

- [ ] **Step 1: Write failing test**

```python
# services/assistant-core/tests/test_vector_store.py
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
        hash="h1",
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
    store.upsert_doc("d1", "a.txt", "h1", 1.0, [("x", [1.0, 0.0]), ("y", [0.0, 1.0])], "mock")
    store.upsert_doc("d1", "a.txt", "h2", 2.0, [("z", [1.0, 0.0])], "mock")
    assert store.stats()["chunk_count"] == 1
    assert store.doc_by_path("a.txt")["hash"] == "h2"
    store.delete_doc("d1")
    assert store.stats() == {"doc_count": 0, "chunk_count": 0}
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_vector_store.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement base protocol**

```python
# vector/store/__init__.py  (empty)
```

```python
# vector/store/base.py
from __future__ import annotations

from typing import Protocol


class VectorStore(Protocol):
    def initialize(self) -> None: ...
    def doc_by_path(self, path: str) -> dict | None: ...
    def upsert_doc(
        self,
        doc_id: str,
        path: str,
        hash: str,
        mtime: float,
        chunks: list[tuple[str, list[float]]],
        model: str,
    ) -> None: ...
    def query(self, vector: list[float], k: int, model: str) -> list[dict]: ...
    def delete_doc(self, doc_id: str) -> None: ...
    def list_docs(self) -> list[dict]: ...
    def stats(self) -> dict: ...
```

- [ ] **Step 4: Implement the SQLite store**

```python
# vector/store/sqlite_vector_store.py
from __future__ import annotations

import math
import sqlite3
from array import array
from pathlib import Path
from uuid import uuid4

_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_docs (
  doc_id TEXT PRIMARY KEY,
  path TEXT UNIQUE,
  hash TEXT,
  mtime REAL,
  chunk_count INTEGER,
  status TEXT,
  indexed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS knowledge_chunks (
  id TEXT PRIMARY KEY,
  doc_id TEXT,
  source TEXT,
  chunk_index INTEGER,
  text TEXT,
  embedding BLOB,
  model TEXT,
  dim INTEGER
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON knowledge_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_model ON knowledge_chunks(model);
"""


def _to_blob(vector: list[float]) -> bytes:
    return array("f", vector).tobytes()


def _from_blob(blob: bytes) -> list[float]:
    arr = array("f")
    arr.frombytes(blob)
    return list(arr)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class SqliteVectorStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def doc_by_path(self, path: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_docs WHERE path = ?", (path,)
            ).fetchone()
        return dict(row) if row else None

    def upsert_doc(self, doc_id, path, hash, mtime, chunks, model) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM knowledge_chunks WHERE doc_id = ?", (doc_id,))
            connection.execute(
                """INSERT INTO knowledge_docs (doc_id, path, hash, mtime, chunk_count, status, indexed_at)
                   VALUES (?, ?, ?, ?, ?, 'indexed', CURRENT_TIMESTAMP)
                   ON CONFLICT(doc_id) DO UPDATE SET
                     path=excluded.path, hash=excluded.hash, mtime=excluded.mtime,
                     chunk_count=excluded.chunk_count, status='indexed',
                     indexed_at=CURRENT_TIMESTAMP""",
                (doc_id, path, hash, mtime, len(chunks)),
            )
            for index, (text, vector) in enumerate(chunks):
                connection.execute(
                    """INSERT INTO knowledge_chunks
                       (id, doc_id, source, chunk_index, text, embedding, model, dim)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (str(uuid4()), doc_id, path, index, text, _to_blob(vector), model, len(vector)),
                )

    def query(self, vector, k, model) -> list[dict]:
        dim = len(vector)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT text, source, chunk_index, embedding FROM knowledge_chunks WHERE model = ? AND dim = ?",
                (model, dim),
            ).fetchall()
        scored = [
            {
                "text": row["text"],
                "source": row["source"],
                "chunk_index": row["chunk_index"],
                "score": _cosine(vector, _from_blob(row["embedding"])),
            }
            for row in rows
        ]
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:k]

    def delete_doc(self, doc_id) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM knowledge_chunks WHERE doc_id = ?", (doc_id,))
            connection.execute("DELETE FROM knowledge_docs WHERE doc_id = ?", (doc_id,))

    def list_docs(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT path, chunk_count, status, indexed_at FROM knowledge_docs ORDER BY path"
            ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict:
        with self._connect() as connection:
            docs = connection.execute("SELECT COUNT(*) AS c FROM knowledge_docs").fetchone()["c"]
            chunks = connection.execute("SELECT COUNT(*) AS c FROM knowledge_chunks").fetchone()["c"]
        return {"doc_count": docs, "chunk_count": chunks}
```

- [ ] **Step 5: Run + verify pass**

Run: `python -m pytest services/assistant-core/tests/test_vector_store.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Log + commit**

Write `logs/sqlite-vector-store_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/vector/store services/assistant-core/tests/test_vector_store.py logs/sqlite-vector-store_2026-07-25_log.md
git commit -m "feat: SQLite vector store with cosine query"
```

---

### Task 4: Un-clipped extraction + knowledge indexer

**Files:**
- Modify: `services/assistant-core/src/violet_assistant/ingestion/extractors.py` (add `max_chars` param)
- Create: `services/assistant-core/src/violet_assistant/knowledge/__init__.py`
- Create: `services/assistant-core/src/violet_assistant/knowledge/indexer.py`
- Test: `services/assistant-core/tests/test_indexer.py`, extend `services/assistant-core/tests/test_ingestion.py`

**Interfaces:**
- Consumes: `extract_text`, `chunk_text`, `EmbeddingProvider`, `SqliteVectorStore`.
- Produces: `extract_text(filename, data, max_chars: int | None = MAX_TEXT_CHARS)`; `KnowledgeIndexer(embedder, store, knowledge_dir, chunk_size, chunk_overlap)` with `async reindex(full=False) -> dict`.

- [ ] **Step 1: Write failing tests**

```python
# services/assistant-core/tests/test_indexer.py
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
    # second run with no changes → skipped
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
async def test_reindex_records_errors_without_crashing(tmp_path):
    indexer, kdir, store = _indexer(tmp_path)
    (kdir / "bad.xyz").write_text("unsupported", encoding="utf-8")
    report = await indexer.reindex()
    assert report["indexed"] == 0
    assert len(report["errors"]) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_indexer.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Add `max_chars` to `extract_text`**

In `ingestion/extractors.py`, change `_clip` + `extract_text` to accept a limit:

```python
def _clip(text: str, max_chars: int | None) -> tuple[str, bool]:
    text = text.strip()
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars].rstrip() + "\n… [truncated]", True
    return text, False
```

Change the signature and final call:

```python
def extract_text(filename: str, data: bytes, max_chars: int | None = MAX_TEXT_CHARS) -> dict:
    ...
    text, truncated = _clip(raw, max_chars)
```

- [ ] **Step 4: Implement the indexer**

```python
# knowledge/__init__.py  (empty)
```

```python
# knowledge/indexer.py
from __future__ import annotations

import hashlib
from pathlib import Path

from violet_assistant.ingestion.extractors import ExtractionError, extract_text
from violet_assistant.vector.chunker import chunk_text

_SUPPORTED = {
    ".txt", ".md", ".markdown", ".log", ".rst",
    ".csv", ".tsv", ".xlsx", ".xlsm", ".pdf", ".docx", ".json",
}


class KnowledgeIndexer:
    def __init__(self, embedder, store, knowledge_dir: Path, chunk_size=1000, chunk_overlap=150):
        self.embedder = embedder
        self.store = store
        self.knowledge_dir = Path(knowledge_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def reindex(self, full: bool = False) -> dict:
        report = {"indexed": 0, "skipped": 0, "removed": 0, "chunks": 0, "errors": []}
        if not self.knowledge_dir.exists():
            return report
        seen_paths: set[str] = set()
        for path in sorted(self.knowledge_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _SUPPORTED:
                continue
            rel = str(path.relative_to(self.knowledge_dir).as_posix())
            seen_paths.add(rel)
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            existing = self.store.doc_by_path(rel)
            if not full and existing and existing["hash"] == digest:
                report["skipped"] += 1
                continue
            try:
                extracted = extract_text(path.name, data, max_chars=None)
                pieces = chunk_text(extracted["text"], self.chunk_size, self.chunk_overlap)
                if not pieces:
                    raise ExtractionError("no chunks produced")
                vectors = await self.embedder.embed(pieces)
                doc_id = existing["doc_id"] if existing else hashlib.sha256(rel.encode()).hexdigest()[:16]
                self.store.upsert_doc(
                    doc_id=doc_id,
                    path=rel,
                    hash=digest,
                    mtime=path.stat().st_mtime,
                    chunks=list(zip(pieces, vectors)),
                    model=self.embedder.name,
                )
                report["indexed"] += 1
                report["chunks"] += len(pieces)
            except Exception as exc:  # noqa: BLE001 — one bad file must not stop the scan
                report["errors"].append({"path": rel, "error": str(exc)})
        # remove docs whose files are gone
        for doc in self.store.list_docs():
            if doc["path"] not in seen_paths:
                existing = self.store.doc_by_path(doc["path"])
                if existing:
                    self.store.delete_doc(existing["doc_id"])
                    report["removed"] += 1
        return report
```

- [ ] **Step 5: Add extractor test + run**

```python
# append to tests/test_ingestion.py
from violet_assistant.ingestion.extractors import extract_text


def test_extract_text_respects_max_chars_none():
    big = ("x" * 50_000).encode("utf-8")
    clipped = extract_text("a.txt", big)  # default clip
    full = extract_text("a.txt", big, max_chars=None)
    assert clipped["truncated"] is True
    assert full["truncated"] is False
    assert full["chars"] >= 50_000
```

Run: `python -m pytest services/assistant-core/tests/test_indexer.py services/assistant-core/tests/test_ingestion.py -q`
Expected: PASS.

- [ ] **Step 6: Log + commit**

Write `logs/knowledge-indexer_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/knowledge services/assistant-core/src/violet_assistant/ingestion/extractors.py services/assistant-core/tests/test_indexer.py services/assistant-core/tests/test_ingestion.py logs/knowledge-indexer_2026-07-25_log.md
git commit -m "feat: knowledge indexer + un-clipped extraction"
```

---

### Task 5: Vector retriever + factory wiring

**Files:**
- Create: `services/assistant-core/src/violet_assistant/rag/vector_retriever.py`
- Modify: `services/assistant-core/src/violet_assistant/rag/factory.py` (add `vector` branch)
- Test: `services/assistant-core/tests/test_vector_retriever.py`, extend `services/assistant-core/tests/test_retriever_seam.py` if needed

**Interfaces:**
- Consumes: `EmbeddingProvider`, `SqliteVectorStore`, `Chunk`.
- Produces: `VectorRetriever(embedder, store, model)` implementing `Retriever`; `create_retriever` supports `RAG_PROVIDER=vector`.

- [ ] **Step 1: Write failing test**

```python
# services/assistant-core/tests/test_vector_retriever.py
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
    store.upsert_doc("d1", "a.txt", "h", 1.0, [("north wall", [1.0, 0.0]), ("east wall", [0.0, 1.0])], "mock")
    retriever = VectorRetriever(_AxisEmbedder(), store, model="mock")
    chunks = await retriever.retrieve("which way is north?", k=1)
    assert len(chunks) == 1
    assert chunks[0].text == "north wall"
    assert chunks[0].source == "a.txt"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_vector_retriever.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement retriever**

```python
# rag/vector_retriever.py
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
```

- [ ] **Step 4: Wire the factory**

Replace `rag/factory.py` body so `vector` builds the retriever:

```python
from __future__ import annotations

from violet_assistant.config import Settings
from violet_assistant.rag.base import Retriever
from violet_assistant.rag.no_op_retriever import NoOpRetriever

NO_OP_PROVIDERS = {"none", "off", "mock", ""}


def create_retriever(settings: Settings) -> Retriever:
    provider = settings.rag_provider.strip().lower()
    if provider in NO_OP_PROVIDERS:
        return NoOpRetriever()
    if provider == "vector":
        from violet_assistant.vector.embeddings.factory import create_embedder
        from violet_assistant.vector.store.sqlite_vector_store import SqliteVectorStore
        from violet_assistant.rag.vector_retriever import VectorRetriever

        store = SqliteVectorStore(settings.knowledge_db)
        store.initialize()
        embedder = create_embedder(settings)
        return VectorRetriever(embedder, store, model=embedder.name)
    supported = sorted((NO_OP_PROVIDERS - {""}) | {"vector"})
    raise ValueError(
        f"Unsupported RAG_PROVIDER={settings.rag_provider!r}. Supported: {', '.join(supported)}."
    )
```

Note: the retriever's `model` is the embedder's `name` (e.g. `"mock"` or `"openai_compatible"`), matching what the indexer stores.

- [ ] **Step 5: Run + verify pass**

Run: `python -m pytest services/assistant-core/tests/test_vector_retriever.py services/assistant-core/tests/test_retriever_seam.py -q`
Expected: PASS.

- [ ] **Step 6: Log + commit**

Write `logs/vector-retriever_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/rag/vector_retriever.py services/assistant-core/src/violet_assistant/rag/factory.py services/assistant-core/tests/test_vector_retriever.py logs/vector-retriever_2026-07-25_log.md
git commit -m "feat: vector retriever + RAG_PROVIDER=vector wiring"
```

---

### Task 6: Knowledge routes + main wiring + retrieved-source citations

**Files:**
- Create: `services/assistant-core/src/violet_assistant/routes/knowledge.py`
- Modify: `services/assistant-core/src/violet_assistant/main.py` (build embedder/store/indexer; include router; guarded startup scan; pass retriever already built)
- Modify: `services/assistant-core/src/violet_assistant/orchestrator/chat_orchestrator.py` (append retrieved sources to `citations`)
- Test: `services/assistant-core/tests/test_knowledge_routes.py`, extend `tests/test_chat_orchestrator.py`

**Interfaces:**
- Consumes: `KnowledgeIndexer`, `SqliteVectorStore`, `Settings`.
- Produces: `GET /api/knowledge`, `POST /api/knowledge/reindex`; orchestrator adds retrieved chunk sources to `ChatResponse.citations`.

- [ ] **Step 1: Write failing route tests**

```python
# services/assistant-core/tests/test_knowledge_routes.py
from __future__ import annotations

import pytest

from violet_assistant.knowledge.indexer import KnowledgeIndexer
from violet_assistant.routes.knowledge import create_knowledge_router
from violet_assistant.vector.embeddings.mock_embedder import MockEmbedder
from violet_assistant.vector.store.sqlite_vector_store import SqliteVectorStore


def _get(router, method):
    for route in router.routes:
        if method in route.methods:
            yield route.endpoint


@pytest.mark.asyncio
async def test_knowledge_status_and_reindex(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "a.txt").write_text("hello", encoding="utf-8")
    store = SqliteVectorStore(tmp_path / "k.db")
    store.initialize()
    indexer = KnowledgeIndexer(MockEmbedder(), store, kdir)
    router = create_knowledge_router(indexer, store, str(kdir), "mock")

    endpoints = {tuple(sorted(r.methods)): r.endpoint for r in router.routes}
    get_ep = next(e for m, e in endpoints.items() if "GET" in m)
    post_ep = next(e for m, e in endpoints.items() if "POST" in m)

    before = await get_ep()
    assert before["doc_count"] == 0
    report = await post_ep(type("B", (), {"full": False})())
    assert report["indexed"] == 1
    after = await get_ep()
    assert after["doc_count"] == 1


@pytest.mark.asyncio
async def test_reindex_409_when_no_indexer():
    from fastapi import HTTPException

    router = create_knowledge_router(None, None, "knowledge", "mock")
    post_ep = next(r.endpoint for r in router.routes if "POST" in r.methods)
    with pytest.raises(HTTPException) as exc:
        await post_ep(type("B", (), {"full": False})())
    assert exc.value.status_code == 409
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_knowledge_routes.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement the router**

```python
# routes/knowledge.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class ReindexRequest(BaseModel):
    full: bool = False


def create_knowledge_router(indexer, store, knowledge_dir: str, model: str) -> APIRouter:
    router = APIRouter()

    @router.get("/api/knowledge")
    async def status() -> dict:
        stats = store.stats() if store else {"doc_count": 0, "chunk_count": 0}
        docs = store.list_docs() if store else []
        return {
            "dir": str(knowledge_dir),
            "provider": model,
            "enabled": indexer is not None,
            "doc_count": stats["doc_count"],
            "chunk_count": stats["chunk_count"],
            "docs": docs,
        }

    @router.post("/api/knowledge/reindex")
    async def reindex(body: ReindexRequest) -> dict:
        if indexer is None:
            raise HTTPException(status_code=409, detail="Knowledge base is not enabled (set RAG_PROVIDER=vector).")
        return await indexer.reindex(full=body.full)

    return router
```

- [ ] **Step 4: Wire `main.py`**

Add imports near the others:

```python
from violet_assistant.routes.knowledge import create_knowledge_router
from violet_assistant.knowledge.indexer import KnowledgeIndexer
from violet_assistant.vector.embeddings.factory import create_embedder
from violet_assistant.vector.store.sqlite_vector_store import SqliteVectorStore
```

After `retriever = create_retriever(active_settings)`, add:

```python
    knowledge_indexer = None
    knowledge_store = None
    if active_settings.rag_provider.strip().lower() == "vector":
        knowledge_store = SqliteVectorStore(active_settings.knowledge_db)
        knowledge_store.initialize()
        knowledge_indexer = KnowledgeIndexer(
            embedder=create_embedder(active_settings),
            store=knowledge_store,
            knowledge_dir=active_settings.knowledge_dir,
            chunk_size=active_settings.knowledge_chunk_size,
            chunk_overlap=active_settings.knowledge_chunk_overlap,
        )
        if active_settings.knowledge_scan_on_startup:
            import asyncio

            try:
                asyncio.get_event_loop().run_until_complete(knowledge_indexer.reindex())
            except Exception:  # noqa: BLE001 — startup scan is best-effort
                pass
```

Include the router with the others:

```python
    app.include_router(
        create_knowledge_router(
            knowledge_indexer,
            knowledge_store,
            str(active_settings.knowledge_dir),
            create_embedder(active_settings).name if active_settings.rag_provider.strip().lower() == "vector" else "none",
        )
    )
```

Note: `create_app` is sync; `run_until_complete` at import time can fail if a loop is already running. Guard as shown (best-effort, swallow). If this proves flaky under uvicorn, move the scan to a FastAPI startup event — acceptable follow-up, out of MVP scope.

- [ ] **Step 5: Append retrieved sources to citations (orchestrator)**

In `chat_orchestrator.py`, `retrieved` is already computed:

```python
        retrieved = await self.retriever.retrieve(request.content)
        context = [chunk.text for chunk in retrieved]
```

Capture sources immediately AFTER the `citations: list[str] = []` initialization and BEFORE the precedence ladder:

```python
        citations: list[str] = []
        for chunk in retrieved:
            if chunk.source and chunk.source != "unknown" and chunk.source not in citations:
                citations.append(chunk.source)
```

This ordering is deliberate: the web-search branch reassigns `citations = answer.citations`, so web mode shows only web citations (RAG sources are correctly discarded there), while every non-web path keeps the retrieved sources. `retrieved` is already in scope at this point.

- [ ] **Step 6: Add an orchestrator citation test**

In `tests/test_chat_orchestrator.py`, add a test using a fake retriever returning a `Chunk(source="notes.md")` and assert `response.citations == ["notes.md"]` on a normal (non-mock) provider path. Reuse the file's `_settings`/`_store` helpers; pass `retriever=<fake>` and a non-mock provider (e.g. `MarkerProvider`-style) with `request.provider=None`.

- [ ] **Step 7: Run backend suite**

Run: `python -m pytest -q`
Expected: all PASS. Verify app boot: `PYTHONPATH=services/assistant-core/src python -c "from violet_assistant.main import create_app; from violet_assistant.config import load_settings; import pathlib; create_app(load_settings(pathlib.Path('.').resolve())).openapi()['paths'].keys()"` includes `/api/knowledge`.

- [ ] **Step 8: Log + commit**

Write `logs/knowledge-routes-wiring_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/routes/knowledge.py services/assistant-core/src/violet_assistant/main.py services/assistant-core/src/violet_assistant/orchestrator/chat_orchestrator.py services/assistant-core/tests/test_knowledge_routes.py services/assistant-core/tests/test_chat_orchestrator.py logs/knowledge-routes-wiring_2026-07-25_log.md
git commit -m "feat: knowledge routes + startup scan + retrieved-source citations"
```

---

### Task 7: `ui_mode` preference

**Files:**
- Modify: `services/assistant-core/src/violet_assistant/preferences/store.py` (add `ui_mode`)
- Test: extend `services/assistant-core/tests/test_preferences.py`

**Interfaces:**
- Produces: `ui_mode` editable key, values `user`/`developer`, default `user`.

- [ ] **Step 1: Write failing test**

```python
# append to tests/test_preferences.py
def test_ui_mode_default_and_validation(tmp_path, settings):
    store = PreferencesStore(tmp_path / "preferences.json")
    assert store.effective(settings)["ui_mode"] == "user"
    store.patch({"ui_mode": "developer"})
    assert store.effective(settings)["ui_mode"] == "developer"
    import pytest
    with pytest.raises(ValueError):
        store.patch({"ui_mode": "root"})
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_preferences.py::test_ui_mode_default_and_validation -q`
Expected: FAIL (`ui_mode` unknown key).

- [ ] **Step 3: Add the key + default**

In `preferences/store.py`, add to `EDITABLE_KEYS`:

```python
    "ui_mode": lambda v: v in {"user", "developer"},
```

Add to `_defaults(...)`:

```python
        "ui_mode": "user",
```

- [ ] **Step 4: Run + verify pass**

Run: `python -m pytest services/assistant-core/tests/test_preferences.py -q`
Expected: PASS.

- [ ] **Step 5: Log + commit**

Write `logs/ui-mode-preference_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/preferences/store.py services/assistant-core/tests/test_preferences.py logs/ui-mode-preference_2026-07-25_log.md
git commit -m "feat: ui_mode preference (user/developer)"
```

---

### Task 8: Frontend — Knowledge section + mode switch + gating

**Files:**
- Modify: `apps/web-client/src/lib/api.ts` (`KnowledgeInfo`, `fetchKnowledge`, `reindexKnowledge`)
- Modify: `apps/web-client/src/components/SettingsModal.tsx` (mode switch at top; Knowledge section; gate developer-only sections)
- Modify: `apps/web-client/src/App.tsx` (load knowledge; `devMode`; pass to SettingsModal + FloatingTools + ChatTimeline)
- Modify: `apps/web-client/src/components/FloatingTools.tsx` (hide Skill Lab when not devMode)
- Modify: `apps/web-client/src/components/ChatTimeline.tsx` (dev-only debug line — optional, gate existing info)
- Verify: `cd apps/web-client && npm run build`

**Interfaces:**
- Consumes: `GET /api/knowledge`, `POST /api/knowledge/reindex`, `ui_mode` via `/api/settings`.
- Produces: `KnowledgeInfo` type; `fetchKnowledge()`, `reindexKnowledge(full?)`.

- [ ] **Step 1: Add API helpers**

```typescript
// lib/api.ts
export type KnowledgeDoc = {
  path: string;
  chunk_count: number;
  status: string;
  indexed_at: string;
};

export type KnowledgeInfo = {
  dir: string;
  provider: string;
  enabled: boolean;
  doc_count: number;
  chunk_count: number;
  docs: KnowledgeDoc[];
};

export async function fetchKnowledge(): Promise<KnowledgeInfo> {
  return requestJson<KnowledgeInfo>("/api/knowledge");
}

export async function reindexKnowledge(full = false): Promise<{
  indexed: number;
  skipped: number;
  removed: number;
  chunks: number;
  errors: { path: string; error: string }[];
}> {
  return requestJson("/api/knowledge/reindex", {
    method: "POST",
    body: JSON.stringify({ full }),
  });
}
```

- [ ] **Step 2: App state + devMode**

In `App.tsx`:
- `const [knowledge, setKnowledge] = useState<KnowledgeInfo | null>(null);`
- On mount: `fetchKnowledge().then(setKnowledge).catch(() => setKnowledge(null));`
- `const devMode = appSettings?.values.ui_mode === "developer";`
- Add `async function refreshKnowledge() { try { setKnowledge(await fetchKnowledge()); } catch {} }` and a `handleReindex(full)` that calls `reindexKnowledge(full)` then `refreshKnowledge()` and sets a status toast.
- Pass to `SettingsModal`: `knowledge`, `onReindex={handleReindex}`, `devMode`.
- Pass to `FloatingTools`: `devMode` (hide Skill Lab button when false; keep Skill Lab modal render).
- Pass to `ChatTimeline`: `devMode` (optional debug line).
- Import `KnowledgeInfo`, `fetchKnowledge`, `reindexKnowledge` from `./lib/api`.

- [ ] **Step 3: SettingsModal — mode switch + Knowledge + gating**

Extend `SettingsModalProps` with `knowledge: KnowledgeInfo | null`, `onReindex: (full: boolean) => void`, `devMode: boolean`.

Add a mode switch at the very top of the modal body (before "AI engine"):

```tsx
<div className="flex items-center gap-2 mb-2">
  <span className="text-xs font-semibold text-steel uppercase tracking-wider">Mode</span>
  <div className="ml-auto inline-flex rounded-full bg-steel-ice border border-navy-700/20 p-0.5">
    {(["user", "developer"] as const).map((mode) => (
      <button
        key={mode}
        onClick={() => onPatchSettings({ ui_mode: mode })}
        className={`px-3 py-1 rounded-full text-xs font-medium capitalize transition ${
          (settings?.values.ui_mode ?? "user") === mode
            ? "bg-steel-dark text-white"
            : "text-steel"
        }`}
      >
        {mode}
      </button>
    ))}
  </div>
</div>
```

Wrap the **AI engine**, **Routing cascade**, **Delegate to agent**, and the developer rows of the Behavior block (temperature, web-search model, memory auto-save) in `{devMode && ( ... )}`. Keep Persona, web on/off, canvas, ask-before-saving-memory, and the Knowledge section always visible.

Add the **Knowledge** section (always visible), with the Full-reindex button and per-doc list gated to devMode:

```tsx
{knowledge && (
  <div>
    <label className="block text-xs font-semibold text-steel uppercase tracking-wider mb-2">
      Knowledge base
    </label>
    <div className="p-3 bg-steel-ice rounded-xl border border-navy-700/20 space-y-2">
      <div className="text-[11px] text-steel-dark">
        <span className="font-mono">{knowledge.dir}</span>
      </div>
      <div className="text-[11px] text-steel">
        {knowledge.doc_count} docs · {knowledge.chunk_count} chunks · {knowledge.provider}
      </div>
      {!knowledge.enabled && (
        <div className="text-[11px] text-amber-600">
          Retrieval off — set RAG_PROVIDER=vector to enable.
        </div>
      )}
      <div className="flex gap-2">
        <button
          onClick={() => onReindex(false)}
          disabled={!knowledge.enabled}
          className="flex-1 text-xs font-medium text-steel-highlight bg-steel-highlight/10 hover:bg-steel-highlight/15 border border-steel-highlight/30 rounded-lg py-2 transition disabled:opacity-40"
        >
          Reindex
        </button>
        {devMode && (
          <button
            onClick={() => onReindex(true)}
            disabled={!knowledge.enabled}
            className="flex-1 text-xs font-medium text-steel bg-white border border-navy-700/20 rounded-lg py-2 transition disabled:opacity-40"
          >
            Full rebuild
          </button>
        )}
      </div>
      {devMode && knowledge.docs.length > 0 && (
        <ul className="max-h-28 overflow-y-auto custom-scrollbar space-y-0.5 pt-1">
          {knowledge.docs.map((d) => (
            <li key={d.path} className="text-[11px] text-steel-dark flex justify-between gap-2">
              <span className="truncate">{d.path}</span>
              <span className="text-steel/60 shrink-0">{d.chunk_count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  </div>
)}
```

Gate the existing **Skills → Open Skill Lab** button and the provider/agent sections to devMode as well (per the mapping): wrap the Skills section's "Open Skill Lab" button in `{devMode && (...)}` but keep the skill list visible (using skills is user-facing).

- [ ] **Step 4: FloatingTools — hide Skill Lab in user mode**

Read `FloatingTools.tsx`; add `devMode: boolean` prop and wrap the Skill Lab trigger button in `{devMode && (...)}`. Pass `devMode` from `App`.

- [ ] **Step 5: ChatTimeline — optional dev debug line**

Add `devMode?: boolean` prop; when true and the assistant message has an `agent`, render a tiny muted line like `via agent: {agent}` under the message. (The message currently doesn't carry `agent`; if not readily available, skip this sub-step — it is optional and must not block the build.)

- [ ] **Step 6: Build**

Run: `cd apps/web-client && npm run build`
Expected: clean typecheck + build.

- [ ] **Step 7: Log + commit**

Write `logs/knowledge-ui-and-modes_2026-07-25_log.md`, then:

```bash
git add apps/web-client/src/lib/api.ts apps/web-client/src/components/SettingsModal.tsx apps/web-client/src/App.tsx apps/web-client/src/components/FloatingTools.tsx apps/web-client/src/components/ChatTimeline.tsx logs/knowledge-ui-and-modes_2026-07-25_log.md
git commit -m "feat: knowledge UI section + user/developer mode gating"
```

---

## Final verification (after Task 8)
- `python -m pytest -q` → all PASS.
- App boot exposes `/api/knowledge` (get) and `/api/knowledge/reindex` (post).
- `cd apps/web-client && npm run build` → clean.
- Manual smoke: drop a `.txt`/`.pdf` into `knowledge/`, `POST /api/knowledge/reindex`, ask a related question with `RAG_PROVIDER=vector` → answer references the file and the source appears under the answer. Toggle developer mode in Settings → provider/agent/temperature/Skill Lab appear; toggle back to user → they hide.

## Notes for the implementer
- Read a file before editing; match existing Tailwind (`steel-*`, `navy-*`) and factory/Protocol patterns.
- The embedder's `name` is the `model` tag stored with each chunk and used by the retriever's `query` — they must match (both come from the same `create_embedder`). Do not hardcode `"mock"` in wiring; use `embedder.name`.
- Startup scan is best-effort and swallowed; never let it break boot.
- Keep secrets out of committed files; `EMBED_API_KEY` only via `.env`.
