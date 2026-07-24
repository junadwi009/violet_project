# Directory-based memory backend (Claude-style files)

- **Date:** 2026-07-24
- **Track:** memory / storage
- **Branch:** main
- **Author:** Claude Code

## What
Added a pluggable approved-memory store. New default `files` backend keeps approved memories as
Claude-style markdown files (one per fact + a `MEMORY.md` index) in a configurable directory, so
users manage memory from a local folder — or a VPS mount / Google-Drive-synced folder — instead of
an opaque SQLite table. Candidates stay in SQLite. Design: brainstormed;
`docs/superpowers/specs/2026-07-24-directory-memory-backend-design.md`.

## Why
User wants to manage memory from a cloud-or-local directory (VPS later, Google Drive later), like
Claude/cowork file-based memory. Files are portable, human-editable, and Drive-syncable for free.

## Backend
- `memory/store/base.py` — `ApprovedMemoryStore` protocol + record shape.
- `memory/store/file_store.py` — `FileApprovedMemoryStore`: markdown files with frontmatter +
  regenerated `MEMORY.md` index; filename `<slug>--<id>.md` stable across edits; tiny built-in
  frontmatter parser (no new dependency); `import_record` for migration.
- `memory/store/sqlite_adapter.py` — `SqliteApprovedMemoryStore` over the existing table.
- `memory/store/factory.py` — `create_approved_memory_store` (env `MEMORY_BACKEND`, default `files`)
  + `migrate_sqlite_memories_to_files` (idempotent one-time import).
- `SQLiteStore` gained `get_pending_candidate`, `mark_candidate_approved`, `insert_memory`
  (existing `approve_memory_candidate` kept intact for its unit tests).
- `routes/memory.py` — approve now composes candidate-read → `memory_store.add` → mark approved;
  list/update/delete go through `memory_store`; new `GET /api/memory/info` → `{backend, location}`.
- `config.py` — `MEMORY_BACKEND` (default `files`), `MEMORY_DIR` (default `<repo_root>/memory`).
- `main.py` — build the store, migrate SQLite → files on startup when using the files backend.

## Frontend / infra
- `lib/api.ts` `fetchMemoryInfo`; `MemoryDrawer` header shows backend + directory path.
- `docker-compose.yml` — bind-mount `./memory:/app/memory`, `MEMORY_BACKEND=files`, `MEMORY_DIR=/app/memory`.
- `.env.example`, `.gitignore` (`/memory/`), `.dockerignore`, `DOCKER.md` "Memory storage" section.

## Interfaces / contracts
- New `ApprovedMemoryStore` protocol; `create_memory_router` now takes `(store, memory_store)`.
- `Settings` gained `memory_backend`, `memory_dir` (manual `Settings(...)` builds must pass them).
- New env `MEMORY_BACKEND`, `MEMORY_DIR`. New route `GET /api/memory/info`. Existing memory
  endpoints unchanged in shape.

## Status
done — tests green, live-verified against the file backend.

## Verification
- `python -m pytest` → **32 passed** (+6 file-store tests; existing memory tests still green).
- `npm run build` → clean.
- Live (local uvicorn, `MEMORY_BACKEND=files`): `/api/memory/info` = `files` + dir; chat → candidate
  → approve **wrote `memories/<slug>--<id>.md` + `MEMORY.md`**; `/api/memory` read it back from disk.
- Docker rebuild + bind-mount verification: see below in session (memory files land in host `./memory`).

## Next / future
- Native Google Drive API backend (same interface) — today Drive works via a synced/rclone folder.
- Inject approved memories into chat context (Track 2 RAG). Vector recall over memory (Track 3).
