# Vector store: origin/version columns + per-origin ops

- **Date:** 2026-07-25
- **Track:** 3 Vector
- **Branch:** feat/gdrive-connector
- **Author:** Claude (executing gdrive plan, Task 1)

## What
`SqliteVectorStore` gains `origin` + `version` columns (idempotent migration for
existing DBs: backfills `version=hash`, `origin='local'`). `upsert_doc` now takes
`version` + `origin`; added `doc_by_id`, `delete_missing(origin, seen_ids)`, and
`origin` filters on `list_docs`/`stats`. Minimal `hash→version` follow-through in
the Phase A indexer + one store test to stay green (indexer is fully rewritten in
Task 2).

## Why
Multiple knowledge sources (local + Drive) must coexist in one store with
per-origin incremental sync and cleanup.

## Files touched
- `services/assistant-core/src/violet_assistant/vector/store/sqlite_vector_store.py`
- `services/assistant-core/src/violet_assistant/vector/store/base.py`
- `services/assistant-core/src/violet_assistant/knowledge/indexer.py` (minimal)
- `services/assistant-core/tests/test_vector_store.py`

## Interfaces / contracts changed
- `upsert_doc(doc_id, path, version, mtime, chunks, model, origin='local')`.
- New: `doc_by_id`, `delete_missing`, `list_docs(origin=None)`, `stats(origin=None)`.

## Status
done

## Verification
`python -m pytest -q` → 118 passed. Migration of a simulated old Phase-A DB
verified (version/origin backfilled).

## Next
Task 2: KnowledgeSource protocol + LocalFolderSource + source-based indexer.
