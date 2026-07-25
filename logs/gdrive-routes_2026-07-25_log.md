# Knowledge routes: per-source status + gdrive connect/status/disconnect

- **Date:** 2026-07-25
- **Track:** 2 RAG
- **Branch:** feat/gdrive-connector
- **Author:** Claude (executing gdrive plan, Task 6)

## What
`GET /api/knowledge` now returns a per-source `sources` list; `reindex` accepts
`source` to sync one origin. New `GET /api/knowledge/gdrive/status`,
`POST /api/knowledge/gdrive/connect` (runs the one-time OAuth consent), and
`POST /api/knowledge/gdrive/disconnect` (revokes the token). Router signature
extended with `sources`/`gdrive_source`/`settings` (defaulted, so Phase A 4-arg
callers/tests are unchanged); `main.py` passes them in.

## Why
UI needs source status + a Drive connect/sync/disconnect surface.

## Files touched
- `services/assistant-core/src/violet_assistant/routes/knowledge.py`
- `services/assistant-core/src/violet_assistant/main.py`
- `services/assistant-core/tests/test_knowledge_routes.py`

## Interfaces / contracts changed
- `create_knowledge_router(..., sources=None, gdrive_source=None, settings=None)`.
- New routes `/api/knowledge/gdrive/{status,connect,disconnect}`;
  `reindex {source?}`.

## Status
done

## Verification
`python -m pytest -q` → 130 passed. App boot exposes all five knowledge routes.

## Next
Task 7: frontend sources UI + Drive connect.
