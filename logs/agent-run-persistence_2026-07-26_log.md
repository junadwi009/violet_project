# agent_runs table, multi-migration runner, tool audit writes

- **Date:** 2026-07-26
- **Track:** cross-cutting (agent tool loop, Task 5)
- **Branch:** feat/agent-tool-loop
- **Author:** Claude

## What
Added `database/migrations/002_agent_runs.sql` and taught
`SQLiteStore.initialize()` to apply **every** `*.sql` in the migration file's
parent directory, sorted (it previously read only the single `migration_path`
file). Added `create_agent_run` / `get_agent_run` / `update_agent_run` and
`add_tool_audit_log` / `list_tool_audit_logs` — the latter finally writing to the
`tool_audit_logs` table that has existed unused since `001_init.sql`.

The `migration_path` parameter was kept (rather than switching to a directory
argument) so `create_app` and every existing test call site work unchanged.

## Why
Pause/resume needs the loop state to survive across HTTP requests, and
SECURITY_RULES #6 requires destructive/risky actions to be audited.

## Files touched
- `database/migrations/002_agent_runs.sql` (new)
- `services/assistant-core/src/violet_assistant/persistence/sqlite_store.py`
- `services/assistant-core/tests/test_agent_run_store.py` (new)

## Interfaces / contracts changed
- `initialize()` now applies all migrations in the directory (idempotent —
  every statement is `IF NOT EXISTS`).
- New store methods listed above.

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_agent_run_store.py -q` → 3 passed.
Full suite → **180 passed**.
Migration checked against a **copy of the real `data/violet.db`**: `agent_runs`
present, all 33 existing messages preserved, re-running added nothing.

## ⚠️ Pre-existing issue surfaced (not fixed here — out of scope)
`main.py` ends with a module-level `app = create_app()`. Because
`tests/test_knowledge_routes.py` imports `violet_assistant.main` inside a test,
that import **executes `create_app()` with the real `.env` settings** and so
touches the developer's real `data/violet.db` — which is how `agent_runs`
appeared there before any app restart. Harmless today (DDL is idempotent, no data
lost) but a test suite should never write to the real database.

Suggested fix (separate change): guard the module-level instantiation, e.g. build
`app` lazily via a factory for uvicorn (`uvicorn violet_assistant.main:create_app
--factory`) or skip it when `PYTEST_CURRENT_TEST` is set.

## Next
Task 6: routes + orchestrator wiring.
