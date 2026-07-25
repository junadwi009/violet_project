# Source-abstraction indexer + LocalFolderSource

- **Date:** 2026-07-25
- **Track:** 2 RAG
- **Branch:** feat/gdrive-connector
- **Author:** Claude (executing gdrive plan, Task 2)

## What
New `KnowledgeSource` protocol + `SourceDocument`; the local scan is now
`LocalFolderSource`. `KnowledgeIndexer` takes a list of sources and iterates each
with per-origin incremental skip (by `version`) and per-origin cleanup
(`delete_missing`), returning a per-source report. `main.py` builds the source
list from `KNOWLEDGE_SOURCES` (local by default; gdrive appended when configured).
Added all gdrive `Settings` fields (defaults empty) so boot is safe ahead of
Tasks 3–5.

## Why
Lets local folder and Google Drive feed one pipeline without colliding.

## Files touched
- `services/assistant-core/src/violet_assistant/knowledge/sources/**` (new)
- `services/assistant-core/src/violet_assistant/knowledge/indexer.py` (rewritten)
- `services/assistant-core/src/violet_assistant/main.py` (SHARED SEAM: source list)
- `services/assistant-core/src/violet_assistant/config.py` (sources + gdrive fields)
- `services/assistant-core/tests/test_sources.py` (new), `test_indexer.py` (rewritten),
  `test_knowledge_routes.py` (constructor)

## Interfaces / contracts changed
- `KnowledgeIndexer(embedder, store, sources, ...)`, `reindex(full, only)`.
- `KnowledgeSource` protocol; `SourceDocument`.
- New env `KNOWLEDGE_SOURCES` (+ gdrive fields, empty defaults).

## Status
done

## Verification
`python -m pytest -q` → 120 passed. App boots (default local-only).

## Next
Task 3: Google OAuth helper.
