# Design — Local Knowledge Base (RAG) + User/Developer UI Modes

Date: 2026-07-25
Status: Approved (brainstorming → plan)
Scope: `project_violet` (assistant-core backend + web-client frontend)

## Summary

Two related capabilities:

1. **Local knowledge base (Phase A RAG):** a watched local `knowledge/` folder
   whose files are extracted → chunked → embedded → stored as vectors in SQLite,
   then retrieved and injected into the chat system prompt (with source
   attribution). Nothing leaves the machine with the default mock embedder or a
   local Ollama embed model.
2. **User / Developer UI modes:** a persisted `ui_mode` preference that filters
   which controls the UI exposes — user mode = "use Violet", developer mode =
   "configure/build/debug Violet".

Both build on the existing seams: the `Retriever` protocol + frozen `Chunk`
contract (already injected by the orchestrator) and the `PreferencesStore` +
`/api/settings` added on 2026-07-25.

---

## Part 1 — Knowledge base (RAG)

### Data flow
```
knowledge/ folder → extract text → chunk → embed (Ollama/mock) → SQLite vectors
chat question → embed question → cosine top-k → inject into system prompt + cite
```

### 1. Embeddings (`vector/embeddings/`)
- `base.py`: `class EmbeddingProvider(Protocol)` with
  `async def embed(self, texts: list[str]) -> list[list[float]]` and a `name`.
- `mock_embedder.py` (`MockEmbedder`, name `"mock"`): deterministic — hash each
  token, accumulate into a fixed-dim (256) vector, L2-normalize. Zero setup;
  default; makes the whole pipeline + tests run with no model server.
- `openai_compatible_embedder.py` (`OpenAICompatibleEmbedder`, name
  `"openai_compatible"`): `POST {base_url}/embeddings` with `{model, input}`;
  reads `data[i].embedding`. Works with Ollama (`http://localhost:11434/v1`,
  model `nomic-embed-text`) and any compatible server. Uses stdlib `urllib`
  (same pattern as `OpenAICompatibleProvider`), `asyncio.to_thread` for async.
- `factory.py`: `create_embedder(settings) -> EmbeddingProvider` reading
  `EMBED_PROVIDER` (`mock` default; `openai_compatible`/`ollama` → the HTTP one).

### 2. Vector store (`vector/store/`)
- `base.py`: `class VectorStore(Protocol)` with `upsert_doc`, `query`,
  `delete_doc`, `list_docs`, `stats`, `doc_by_path`.
- `sqlite_vector_store.py` (`SqliteVectorStore`): own SQLite file
  (`KNOWLEDGE_DB`, default `data/knowledge.db`), created idempotently:
  - `knowledge_docs(doc_id TEXT PK, path TEXT UNIQUE, hash TEXT, mtime REAL,
    chunk_count INT, status TEXT, indexed_at TEXT)`
  - `knowledge_chunks(id TEXT PK, doc_id TEXT, source TEXT, chunk_index INT,
    text TEXT, embedding BLOB, model TEXT, dim INT)`
  - embeddings stored as `array('f', vector).tobytes()`; read back via
    `array('f')`.
  - `upsert_doc(path, hash, mtime, chunks: list[(text, vector)], model)`:
    replaces all chunks for that doc atomically (delete-then-insert in a txn).
  - `query(vector, k, model)`: pure-Python cosine over rows with matching
    `model` + `dim`; return top-k `(score, text, source, chunk_index)`.
  - `delete_doc(doc_id)`, `list_docs()`, `stats() -> {doc_count, chunk_count}`.

### 3. Chunker (`vector/chunker.py`)
- Pure `chunk_text(text, size=1000, overlap=150) -> list[str]`: split on blank
  lines into paragraphs, greedily pack to ~`size` chars, carry `overlap` chars
  of tail into the next chunk. Never splits mid-word where avoidable. Drops
  empty chunks.

### 4. Indexer (`knowledge/indexer.py`)
- `class KnowledgeIndexer(embedder, store, knowledge_dir)`.
- `async def reindex(self, full: bool = False) -> dict`: scan `knowledge_dir`
  recursively for supported files. For each:
  - compute `sha256` of bytes; if `not full` and an unchanged doc with the same
    hash exists → **skip**.
  - else `extract_text_full(filename, data)` (un-clipped variant, see below) →
    `chunk_text` → `embedder.embed(chunks)` → `store.upsert_doc(...)`.
  - track filenames seen; after the loop, `delete_doc` any doc whose path is no
    longer present (removed files).
  - `full=True` wipes and rebuilds every doc.
  - returns `{indexed, skipped, removed, chunks, errors:[{path, error}]}`.
- Supported files: reuse `ingestion.extractors` extensions
  (txt/md/csv/tsv/xlsx/pdf/docx/json). Images are skipped in Phase A (logged,
  no OCR ingest yet).
- `extract_text_full`: add a `max_chars: int | None = None` parameter to
  `ingestion.extractors.extract_text` (default keeps current 20k clip for
  uploads; the indexer passes `None` to disable clipping).

### 5. Retriever (`rag/vector_retriever.py`)
- `class VectorRetriever(embedder, store, model)` implementing `Retriever`:
  `retrieve(query, k=4)` → `embedder.embed([query])[0]` → `store.query(vec, k,
  model)` → `[Chunk(text, source, score, metadata={"chunk_index": ...})]`.
- `rag/factory.py`: add a `"vector"` branch to `create_retriever` (build the
  embedder + store + retriever). Unknown providers still fail loudly.

### 6. Routes (`routes/knowledge.py`)
- `GET /api/knowledge` → `{dir, provider, model, doc_count, chunk_count,
  docs:[{path, chunk_count, status, indexed_at}]}`.
- `POST /api/knowledge/reindex` `{full?: bool}` → runs `indexer.reindex`, returns
  the report. Guarded: 409 if no indexer is configured (RAG off).

### 7. Startup + config
- On boot, if `RAG_PROVIDER=vector` and `KNOWLEDGE_SCAN_ON_STARTUP` (default
  true): run `indexer.reindex()` best-effort, wrapped so a failure never blocks
  boot (logged). Incremental hash-skip keeps subsequent boots fast.
- New env / `Settings` fields:
  `knowledge_dir` (`knowledge/`), `knowledge_db` (`data/knowledge.db`),
  `embed_provider` (`mock`), `embed_base_url` (`http://localhost:11434/v1`),
  `embed_model` (`nomic-embed-text`), `embed_api_key?`,
  `knowledge_scan_on_startup` (true), `knowledge_chunk_size` (1000),
  `knowledge_chunk_overlap` (150). `RAG_PROVIDER=vector` activates retrieval.
- Changing `EMBED_MODEL` changes vector dimension → requires `reindex
  {full:true}`; documented in README/env comment.

### 8. Frontend (knowledge section)
- `lib/api.ts`: `fetchKnowledge()`, `reindexKnowledge(full?)` + `KnowledgeInfo`
  type.
- Settings modal gains a **Knowledge** section: folder path, doc/chunk counts,
  document list, **Reindex** button (full reindex only shown in developer mode).
- Retrieved sources already surface via the existing citations UI: the
  orchestrator adds retrieved chunk sources to `ChatResponse.citations` (dedup
  with web citations) so the timeline lists them under the answer.

---

## Part 2 — User / Developer UI modes

### Preference
- Add `ui_mode` to `PreferencesStore.EDITABLE_KEYS` — validator: value in
  `{"user", "developer"}`. Default `"user"`. Persisted in
  `data/preferences.json` like the rest; exposed through `/api/settings`.

### Frontend gating
- `App` derives `devMode = appSettings?.values.ui_mode === "developer"` and
  threads it to the surfaces below. A single source of truth; no per-component
  fetching.
- **Settings modal** shows a mode switch at the top (`User | Developer`), calling
  `onPatchSettings({ ui_mode })`. Sections are gated:
  - Always: Persona, simple toggles (web on/off, canvas, ask-before-saving
    memory), Knowledge (view + Reindex), Palette.
  - Developer only: AI engine/provider, Routing cascade, Temperature + model
    fields, Agent delegation, Skill Lab button, web-search model field, memory
    auto-save, Knowledge advanced (embed provider/model text, Full reindex),
    "overridden" indicators.
- **FloatingTools**: hide the Skill Lab button when `!devMode`.
- **Composer**: unchanged (its controls — attach, web globe, mic, `/` palette —
  are all user-facing). The provider label button opens Settings as today; in
  user mode Settings simply won't show provider internals.
- **ChatTimeline**: show developer debug line (provider/agent used) only in
  `devMode` — requires the response to carry which path was used (already has
  `agent`; add nothing new for MVP, just gate the existing info).

### Mapping table (authoritative)
| Control | user | developer |
|---|---|---|
| Chat / attach / voice | ✅ | ✅ |
| Persona | ✅ | ✅ |
| `/` skill palette (use) | ✅ | ✅ |
| Canvas viewing | ✅ | ✅ |
| Web search on/off | ✅ | ✅ |
| Memory drawer + ask-before-saving | ✅ | ✅ |
| Knowledge: view + Reindex | ✅ | ✅ |
| AI engine / provider | ❌ | ✅ |
| Routing cascade internals | ❌ | ✅ |
| Temperature / model fields | ❌ | ✅ |
| Agent delegation | ❌ | ✅ |
| Skill Lab (vet/merge/install) | ❌ | ✅ |
| Knowledge advanced (embed model, full reindex, stats) | ❌ | ✅ |
| Memory auto-save toggle | ❌ | ✅ |
| Web-search model field | ❌ | ✅ |
| Debug info (provider/agent used) | ❌ | ✅ |

Switching modes is a **free toggle** (local single-user app; no PIN).

---

## Error handling
- Embedder unreachable (Ollama down) → `reindex` records per-file errors; the
  endpoint returns 200 with the error report rather than 500. Startup scan
  failure is swallowed + logged.
- `query` with no matching-model chunks → empty list → chat behaves as pre-RAG.
- Unsupported/empty files → counted in `errors`, never crash the scan.
- `POST /api/knowledge/reindex` when RAG off → 409 with a clear message.
- Invalid `ui_mode` value → 422 from the settings store (existing validation).

## Testing
- `chunk_text`: sizes, overlap, paragraph boundaries, empty input (pure).
- `MockEmbedder`: deterministic, normalized, fixed dim (pure).
- `SqliteVectorStore`: upsert/query/delete/stats; cosine ranks a planted nearest
  vector first; model/dim mismatch excluded (tmp sqlite).
- `KnowledgeIndexer`: incremental hash-skip; removed-file cleanup; full rebuild;
  error captured for a bad file — using `MockEmbedder` + a tmp `knowledge/` dir.
- `VectorRetriever`: returns top-k `Chunk`s with `source` set, using a small
  controlled embedder so nearest-neighbour is deterministic.
- `extract_text(max_chars=None)`: no clip vs default clip.
- Routes (`/api/knowledge`, `/api/knowledge/reindex`, `ui_mode` patch): via
  direct endpoint-callable invocation (no TestClient/httpx — matches existing
  test style).
- Frontend: `npm run build` typecheck + manual smoke.

## Build order
1. `EmbeddingProvider` + `MockEmbedder` + `OpenAICompatibleEmbedder` + factory.
2. `chunk_text`.
3. `SqliteVectorStore`.
4. `extract_text(max_chars=None)` param; `KnowledgeIndexer`.
5. `VectorRetriever` + `rag/factory` `vector` branch + `Settings` fields.
6. `routes/knowledge.py`; `main.py` wiring + guarded startup scan; retrieved
   sources → `ChatResponse.citations`.
7. `ui_mode` in preferences (EDITABLE_KEYS).
8. Frontend: `lib/api.ts` (knowledge + no api change for ui_mode beyond settings)
   ; Settings **Knowledge** section; mode switch + gating across Settings /
   FloatingTools / ChatTimeline.

Each unit: tests where applicable + a `logs/{update}_{date}_log.md` entry before
commit.

## Out of scope (later)
Google Drive connector (Phase C), file-watcher auto-sync (Phase B),
reranking/hybrid BM25, OCR ingestion of images, a full-page Knowledge manager,
PIN-gated developer mode, streaming.
