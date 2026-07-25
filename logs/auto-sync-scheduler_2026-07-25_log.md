# AutoSyncScheduler (interval polling, per-source cadence)

- **Date:** 2026-07-25
- **Track:** 2 RAG
- **Branch:** feat/knowledge-auto-sync
- **Author:** Claude (executing Phase B plan, Task 2)

## What
`AutoSyncScheduler`: reads the `knowledge_auto_sync` pref live; `run_due(now)`
re-runs the incremental reindex — local every tick, gdrive only when its
interval elapses — with an overlap lock, per-source last-sync/error tracking, and
a `status()` block. Thin `start()`/`stop()` loop over `asyncio.sleep`.

## Why
Background auto-sync so the user never clicks Reindex/Sync (Phase B).

## Files touched
- `services/assistant-core/src/violet_assistant/knowledge/auto_sync.py` (new)
- `services/assistant-core/tests/test_auto_sync.py` (new)

## Interfaces / contracts changed
- New: `AutoSyncScheduler(indexer, preferences, settings)` with
  `enabled/run_due/status/start/stop`.

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_auto_sync.py -q` → 6 passed
(disabled no-op, local-every-tick + gdrive-gated cadence, overlap guard, error
capture, status shape).

## Next
Task 3: app wiring + auto_sync in knowledge status.
