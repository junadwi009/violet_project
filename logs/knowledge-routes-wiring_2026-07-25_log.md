# Knowledge routes + startup scan + retrieved-source citations

- **Date:** 2026-07-25
- **Track:** 2 RAG / 1 Chat
- **Branch:** feat/knowledge-base-and-ui-modes
- **Author:** Claude (executing knowledge-base plan, Task 6)

## What
`GET /api/knowledge` (status + doc list) and `POST /api/knowledge/reindex`
(`{full?}`, 409 when RAG off). `main.py` builds the embedder/store/indexer when
`RAG_PROVIDER=vector` and runs a best-effort incremental scan on startup. The
orchestrator now appends retrieved chunk sources to `ChatResponse.citations`
(before the branch ladder, so the web branch's reassignment keeps web mode clean).

## Why
Expose knowledge status/reindex to the UI and attribute answers to source files.

## Files touched
- `services/assistant-core/src/violet_assistant/routes/knowledge.py` (new)
- `services/assistant-core/src/violet_assistant/main.py` (SHARED SEAM: wiring + startup scan)
- `services/assistant-core/src/violet_assistant/orchestrator/chat_orchestrator.py` (SHARED SEAM: citations)
- `services/assistant-core/tests/test_knowledge_routes.py` (new)
- `services/assistant-core/tests/test_chat_orchestrator.py` (citation test)

## Interfaces / contracts changed
- New routes `GET /api/knowledge`, `POST /api/knowledge/reindex`.
- `ChatResponse.citations` now also carries retrieved KB sources.

## Status
done

## Verification
`python -m pytest -q` → 115 passed. App boot exposes both knowledge routes.

## Next
Task 7: `ui_mode` preference.
