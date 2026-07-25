# Wire auto-sync scheduler + expose auto_sync status

- **Date:** 2026-07-25
- **Track:** 2 RAG
- **Branch:** feat/knowledge-auto-sync
- **Author:** Claude (executing Phase B plan, Task 3)

## What
`create_app` builds an `AutoSyncScheduler` when RAG is active, starts it on the
FastAPI `startup` event and stops it on `shutdown`. `GET /api/knowledge` now
returns an `auto_sync` block (enabled, intervals, per-source last-sync). Router
signature gains `scheduler=None` (defaulted, so earlier call sites/tests are
unchanged).

## Why
Run the background loop under uvicorn and surface its state to the UI.

## Files touched
- `services/assistant-core/src/violet_assistant/main.py` (SHARED SEAM: lifecycle)
- `services/assistant-core/src/violet_assistant/routes/knowledge.py`
- `services/assistant-core/tests/test_knowledge_routes.py`

## Interfaces / contracts changed
- `create_knowledge_router(..., scheduler=None)`; `GET /api/knowledge` → `auto_sync`.
- App registers startup/shutdown handlers to start/stop the loop.

## Status
done

## Verification
`python -m pytest -q` → 138 passed. App boots; 1 startup + 1 shutdown handler
registered; `auto_sync` present in the knowledge status.

## Next
Task 4: frontend auto-sync toggle + last-sync display.
