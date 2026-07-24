# Directory-Based Memory Backend — Design Spec

**Date:** 2026-07-24
**Status:** Approved via brainstorming (user chose file-directory memory, Claude-style)

## Goal
Let users manage memory from a **directory** (local now, VPS-mounted later, Google-Drive-synced
later) as human-editable markdown files — like Claude's file-based memory — instead of an opaque
SQLite table. Keep the approval gate.

## Decisions
1. **File-based memory**, Claude-style: a directory with a `MEMORY.md` index + one markdown file
   per approved memory (YAML-ish frontmatter + body). Path configurable via `MEMORY_DIR`.
2. **Pluggable `ApprovedMemoryStore`** interface (same provider pattern as LLM/RAG). Backends:
   `files` (new, **default**), `sqlite` (kept), `gdrive` (future — same interface).
3. **Approved memories = files. Candidates stay in SQLite** (transient pre-approval inbox).
   Approving a candidate writes a markdown file.
4. **Google Drive** is near-free: point `MEMORY_DIR` at a Drive-synced / rclone-mounted folder.
   A native Drive-API backend is a later slot behind the same interface.
5. No new Python dependency — frontmatter is written/parsed with a tiny built-in helper (no PyYAML).

## File format
```
<MEMORY_DIR>/
  MEMORY.md              # index, regenerated on each write: one line per memory
  memories/
    <slug>--<id>.md      # stable filename keyed by id
```
Each memory file:
```
---
id: <uuid>
memory_type: profile
source: message:<id>
confidence: 0.65
created_at: 2026-07-24T09:00:00+00:00
updated_at: 2026-07-24T09:00:00+00:00
---
<the fact text>
```

## Backend interface (`memory/store/base.py`)
`ApprovedMemoryStore`: `list() -> list[dict]`, `add(memory_type, content, source, confidence,
candidate_id=None) -> dict`, `update(id, content, memory_type=None) -> dict`, `delete(id) -> dict`,
`backend_name`, `location()`. Dicts match the current `/api/memory` shape (id, memory_type, content,
source, confidence, approved, created_at, updated_at) so the API and frontend are unchanged.

## Backend changes
- **`FileApprovedMemoryStore`** — new; reads/writes the directory + index.
- **`SqliteApprovedMemoryStore`** — thin adapter over existing `SQLiteStore` memory methods.
- **`SQLiteStore`** gains `get_pending_candidate(id)`, `mark_candidate_approved(id)`,
  `insert_memory(...)`. Existing `approve_memory_candidate` kept intact (unit tests use it).
- **`routes/memory.py`** — inject both `store` (candidates) and `memory_store` (approved);
  approve = read candidate → `memory_store.add` → mark candidate approved. New `GET /api/memory/info`
  → `{backend, location}`.
- **`config.py`** — `MEMORY_BACKEND` (default `files`), `MEMORY_DIR` (default `<repo_root>/memory`).
- **One-time migration** — on startup with the files backend, import any existing SQLite approved
  memories into the directory (id-preserving, idempotent).

## Frontend
- `lib/api.ts`: `fetchMemoryInfo()`. `MemoryDrawer` header shows the active backend + directory path
  (e.g. "files · /app/memory"). No workflow change — approve/edit/delete hit the same endpoints.

## Docker
- Bind-mount a host folder for memory so it's directly manageable: `./memory:/app/memory` with
  `MEMORY_DIR=/app/memory`. SQLite stays in the `violet-data` volume. Documented in DOCKER.md.
- `.gitignore` the `memory/` data dir (personal data).

## Testing
- `test_file_memory_store.py`: add/list/update/delete, frontmatter round-trip, index regeneration,
  id-stable filename.
- Factory default = files; migration idempotency. Existing memory tests stay green.

## Out of scope (later)
Native Google Drive API backend, vector/semantic recall over memory (Track 3), memory injected into
chat context (Track 2).
