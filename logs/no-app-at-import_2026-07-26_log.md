# Fix: importing violet_assistant.main no longer builds the app (or touches the real DB)

- **Date:** 2026-07-26
- **Track:** cross-cutting
- **Branch:** fix/no-app-at-import
- **Author:** Claude

## What
`main.py` ended with a module-level `app = create_app()`. Any import of the
module therefore ran the whole app factory with the developer's real `.env` —
opening and migrating the real `data/violet.db`. Since
`tests/test_knowledge_routes.py` imports the module to reach `create_app`, **the
test suite was writing to the real database.**

Replaced the eager instantiation with a PEP 562 module-level `__getattr__` that
builds `app` on first attribute access and caches it.

## Why
A test suite must never touch the developer's real data. Discovered while adding
the `002_agent_runs.sql` migration: `agent_runs` appeared in `data/violet.db`
before any app restart, which traced back to a test run.

## Why this approach (not `--factory`)
`uvicorn violet_assistant.main:app` is referenced in `README.md` (x2),
`CLAUDE.md`, `services/assistant-core/README.md` and the **Dockerfile CMD**.
Switching to `uvicorn ... --factory create_app` would break all five. Uvicorn
resolves `main:app` with `getattr(module, "app")`, which triggers `__getattr__`
— so the documented command is byte-for-byte unchanged while plain imports stay
side-effect free.

## Files touched
- `services/assistant-core/src/violet_assistant/main.py`
- `services/assistant-core/tests/test_app_import.py` (new)

## Interfaces / contracts changed
- none. `violet_assistant.main:app` still resolves to a `FastAPI` instance;
  it is now created on first access instead of at import.

## Status
done

## Verification
- The regression test **fails on the old code** and passes on the new
  (`"app" not in vars(module)` after import).
- `python -m pytest -q` → **187 passed**.
- **Real DB untouched by the suite:** `data/violet.db` mtime *and* sha256 are
  byte-identical before and after a full run (previously the file was modified).
- Suite runtime dropped from ~28s to ~10s — tests were paying for a full app
  build on import.
- `uvicorn violet_assistant.main:app` starts normally: `Application startup
  complete`, `/health` 200, `/api/knowledge` reports 1 doc with auto-sync on,
  `/api/agents` lists 17 agents.

## Next
none — this closes the follow-up noted in
`agent-run-persistence_2026-07-26_log.md`.
