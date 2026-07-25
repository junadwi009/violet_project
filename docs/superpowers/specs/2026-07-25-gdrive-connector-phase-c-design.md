# Design — Google Drive Connector (Knowledge Base Phase C)

Date: 2026-07-25
Status: Approved (brainstorming → spec). Implementation plan not yet written.
Scope: `project_violet` (assistant-core backend + web-client frontend)
Depends on: Phase A knowledge base (embeddings, `SqliteVectorStore`,
`KnowledgeIndexer`, `VectorRetriever`, `/api/knowledge`).

## Summary

Add Google Drive as a second knowledge source that feeds the **same** ingestion
pipeline as the local folder. A source abstraction is introduced so the local
scan and the Drive connector are interchangeable and can run together. Auth is
**OAuth (installed-app / loopback)** with read-only scope; sync is manual +
startup, incremental by Drive checksum/modifiedTime. Native Google Workspace
files are exported to text; binaries are downloaded. **Shared Drives** are
supported.

Guiding principle unchanged: secrets (OAuth client secrets, refresh token) stay
out of git and out of code; only behavior prefs are runtime-editable. Drive is
**read-only** — Violet never writes to Drive.

---

## Part 1 — Source abstraction (enabling refactor)

Today `KnowledgeIndexer` scans a local directory directly. Phase C generalizes
this so multiple sources feed one store.

### `knowledge/sources/base.py`
```python
@dataclass(frozen=True)
class SourceDocument:
    doc_id: str          # namespaced, stable: "local:<relpath>" | "gdrive:<fileId>"
    display_path: str     # human label shown in UI (relpath or Drive path/name)
    version: str          # change token: content hash | md5Checksum | modifiedTime
    filename: str         # name with extension, drives extractor selection
    mime: str             # source mime (for export decisions)

class KnowledgeSource(Protocol):
    name: str             # "local" | "gdrive" (also the `origin`)
    def status(self) -> dict: ...                     # {name, connected, detail, ...}
    def list_documents(self) -> Iterable[SourceDocument]: ...
    def read(self, doc: SourceDocument) -> bytes: ...  # extracted-ready bytes
```

### `knowledge/sources/local_folder.py`
Refactor the current scan into `LocalFolderSource` (origin `local`). `version` =
SHA-256 of file bytes; `read` returns the file bytes; `list_documents` filters by
the existing supported extensions. Behavior identical to Phase A.

### Indexer becomes source-agnostic
`KnowledgeIndexer(embedder, store, sources: list[KnowledgeSource], chunk_size,
chunk_overlap)`:
- `reindex(full=False, only: str | None = None)` iterates each enabled source
  (optionally a single `only` origin).
- Per document: if `not full` and `store.doc_by_id(doc_id).version == version` →
  skip; else `source.read(doc)` → `extract_text(filename, bytes, max_chars=None)`
  → `chunk_text` → `embed` → `store.upsert_doc(...)` (now also storing `origin`
  and `version`).
- **Per-origin cleanup:** after a source's pass, delete only that origin's docs
  whose `doc_id` was not seen this run. Syncing Drive never removes local docs.
- Report gains a per-source breakdown:
  `{sources: {local: {...}, gdrive: {...}}, indexed, skipped, removed, chunks, errors}`.

### Vector store changes (`SqliteVectorStore`)
- `knowledge_docs` gains `origin TEXT` and `version TEXT` columns (added via
  `ALTER TABLE ... ADD COLUMN` guarded by a PRAGMA check; existing rows default
  `origin='local'`, `version=hash`). `knowledge_chunks` also gains `origin` for
  fast per-origin queries (optional; can filter via join on `doc_id`).
- New/changed methods: `doc_by_id(doc_id)`, `upsert_doc(..., origin, version)`,
  `list_docs(origin=None)`, `delete_missing(origin, seen_ids: set[str])`,
  `stats(origin=None)`.
- `query()` is unchanged (still model+dim scoped); retrieval spans all origins.

---

## Part 2 — Google Drive source

### `knowledge/gdrive_auth.py` (OAuth)
- Uses `google-auth-oauthlib` `InstalledAppFlow.run_local_server(port=0)` — a
  loopback consent. Scope: `["https://www.googleapis.com/auth/drive.readonly"]`.
- Client secrets loaded from `GOOGLE_OAUTH_CLIENT_SECRETS` (path to the JSON from
  Google Cloud Console). Refresh token + creds persisted to `GDRIVE_TOKEN_PATH`
  (default `data/gdrive_token.json`, gitignored).
- `load_credentials()` → returns valid `Credentials` (refreshing silently) or
  `None` if not yet authorized. `authorize()` runs the interactive flow (opens
  the browser on the machine running the backend — correct for local-first) and
  writes the token file. `revoke()` deletes the token file.
- CLI fallback: `python -m violet_assistant.knowledge.gdrive_auth` runs
  `authorize()` from a terminal.

### `knowledge/sources/google_drive.py` (`GoogleDriveSource`)
- Lazy-imports `googleapiclient.discovery.build` + `gdrive_auth`, so importing
  the app without the Drive libs (or without config) never fails — Drive simply
  reports `connected=false`.
- `status()` → `{name:"gdrive", connected: bool, folder_id, shared_drive_id,
  detail: "connected" | "needs_auth" | "not_configured" | "<error>"}`.
- `list_documents()`:
  - Recursively walk `GDRIVE_FOLDER_ID` via `files.list` with
    `q="'<folderId>' in parents and trashed=false"`, paginating; recurse into
    subfolders (`mimeType == application/vnd.google-apps.folder`).
  - **Shared Drives:** always pass `supportsAllDrives=True,
    includeItemsFromAllDrives=True`. If `GDRIVE_SHARED_DRIVE_ID` is set, also pass
    `corpora="drive", driveId=<id>`; otherwise `corpora="allDrives"`. This covers
    both a My Drive folder and a Shared Drive folder.
  - Fields: `id, name, mimeType, md5Checksum, modifiedTime, size, parents`.
  - Build `display_path` from the folder-relative path; `version` =
    `md5Checksum` if present else `modifiedTime`; `doc_id = "gdrive:" + id`.
  - Skip files whose (mapped) type isn't ingestable.
- `read(doc)`:
  - **Native Google types** → `files.export_media`:
    - `application/vnd.google-apps.document` → `text/markdown` (fallback
      `text/plain`), filename `<name>.md`.
    - `application/vnd.google-apps.spreadsheet` → `text/csv`, filename
      `<name>.csv` (Drive export returns the first sheet; multi-tab export is a
      documented limitation — noted in UI/logs).
    - `application/vnd.google-apps.presentation` → `text/plain`, filename
      `<name>.txt`.
  - **Binary types** (PDF/DOCX/XLSX/CSV/TXT/MD/JSON) → `files.get_media`,
    filename `<name>`.
  - Returns bytes; the indexer's `extract_text` picks the extractor from the
    filename extension (export sets the right extension).
  - `export_media` has a ~10 MB server limit; oversized native exports are
    recorded as a per-file error, not a crash.

### Filename/extension mapping
A small `mime → (export_mime, extension)` table lives in `google_drive.py`; the
extension it appends is what `extract_text` keys on, so no extractor changes are
needed. Unmapped mimes are skipped.

---

## Part 3 — Config / env

New `Settings` fields (defaults keep Drive off):
| Env | Default | Meaning |
|---|---|---|
| `KNOWLEDGE_SOURCES` | `local` | comma list: `local`, `gdrive` |
| `GDRIVE_FOLDER_ID` | `""` | folder to mirror (My Drive or Shared Drive) |
| `GDRIVE_SHARED_DRIVE_ID` | `""` | set when the folder lives in a Shared Drive |
| `GOOGLE_OAUTH_CLIENT_SECRETS` | `""` | path to OAuth client JSON |
| `GDRIVE_TOKEN_PATH` | `data/gdrive_token.json` | stored refresh token (gitignored) |
| `GDRIVE_EXPORT_DOC` | `text/markdown` | Docs export mime |

`gdrive` is only active when `KNOWLEDGE_SOURCES` includes it **and**
`GDRIVE_FOLDER_ID` + `GOOGLE_OAUTH_CLIENT_SECRETS` are set. `.gitignore` gets
`data/gdrive_token.json` and any client-secrets path.

---

## Part 4 — Routes & wiring

- `GET /api/knowledge` extended: add `sources: [{name, connected, detail,
  folder_id?, doc_count, last_sync?}]` alongside the existing aggregate counts.
- `POST /api/knowledge/reindex` `{full?, source?}` → runs all enabled sources, or
  just `source` (`local`/`gdrive`); returns the per-source report.
- `POST /api/knowledge/gdrive/connect` → runs `gdrive_auth.authorize()` (opens
  browser on the backend host); returns the new status. Long-running/interactive
  — documented as a one-time local action.
- `GET /api/knowledge/gdrive/status` → the Drive source `status()`.
- `POST /api/knowledge/gdrive/disconnect` → `revoke()` (deletes token file).
- `main.py` builds the source list from `KNOWLEDGE_SOURCES` (guarded, lazy) and
  passes it to `KnowledgeIndexer`; startup scan unchanged (best-effort).

---

## Part 5 — Frontend

- `lib/api.ts`: extend `KnowledgeInfo` with `sources`; add `connectGDrive()`,
  `gdriveStatus()`, `disconnectGDrive()`, and a `source?` arg to
  `reindexKnowledge`.
- Settings **Knowledge base** section grows a **Sources** list:
  - **Local folder** — path + doc count + Reindex (as today).
  - **Google Drive** — connection state (`Connected` / `Not authorized` /
    `Not configured`), folder id, last sync, a **Connect Google Drive** button
    (POST connect), **Reindex Drive**, and (developer mode) **Disconnect**.
- Connect is a one-time action; the UI explains the browser consent will open on
  the machine running Violet.

---

## Dependencies

Add (core, per decision): `google-api-python-client`, `google-auth`,
`google-auth-oauthlib`. All are **lazy-imported** inside `gdrive_auth.py` /
`google_drive.py`; the app boots and the local source works even if they are
absent or Drive is unconfigured. `pyproject.toml` also exposes them as an
optional `drive` extra for clarity.

## Error handling
- Not authorized / revoked / expired-unrefreshable → source `status.detail =
  "needs_auth"`; reindex records a source-level error and continues with other
  sources; never 500s.
- Missing Drive libs → `detail = "library_missing"`; connector dormant.
- Export/download failure or oversized export → per-file error in the report.
- `connect` when client secrets absent → 400 with guidance.
- `reindex?source=gdrive` when Drive disabled → 409.

## Testing (no network / no real credentials)
- `SqliteVectorStore`: `origin`/`version` migration on an old DB; `doc_by_id`;
  `delete_missing(origin, seen_ids)` scoping; `stats(origin)`.
- `KnowledgeIndexer` with a **fake source**: multi-source pass; per-origin
  incremental skip (unchanged `version`); per-origin cleanup (removing a Drive
  doc leaves local docs intact).
- `GoogleDriveSource` with an **injected fake Drive client**: recursive listing
  (incl. subfolders), Shared-Drive params passed, native export vs binary
  download path selection, mime→extension mapping, unmapped-mime skip.
- `gdrive_auth`: token load/refresh/revoke against a temp token file with a fake
  creds object (no real OAuth).
- Routes: status shape; `reindex?source=` routing; 409/400 guards — via direct
  endpoint-callable invocation (existing style, no TestClient).
- Frontend: `npm run build` typecheck.

## Build order (for the eventual plan)
1. Store: `origin`/`version` columns + migration + `doc_by_id` /
   `delete_missing` / `stats(origin)`.
2. `KnowledgeSource` protocol + `SourceDocument`; refactor local scan into
   `LocalFolderSource`; make `KnowledgeIndexer` source-list based (local-only
   still green).
3. `gdrive_auth` (OAuth load/authorize/refresh/revoke) + CLI.
4. `GoogleDriveSource` (list/export/download, Shared Drive, mime map) with a fake
   client in tests.
5. Config fields + `KNOWLEDGE_SOURCES` wiring in `main.py`; dependency extra.
6. Routes: per-source status, `gdrive/connect|status|disconnect`, reindex
   `source` filter.
7. Frontend Sources UI + connect flow.

Each unit: tests + a `logs/{update}_{date}_log.md` entry before commit.

## Out of scope
File-watcher / Drive push webhooks (real-time), Drive `changes`-API cursor,
multi-tab Sheets export, write-back to Drive, per-file Drive ACL mapping,
non-Google cloud sources (Dropbox/OneDrive).
