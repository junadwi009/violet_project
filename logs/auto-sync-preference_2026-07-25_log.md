# knowledge_auto_sync preference + interval settings

- **Date:** 2026-07-25
- **Track:** cross-cutting
- **Branch:** feat/knowledge-auto-sync
- **Author:** Claude (executing Phase B plan, Task 1)

## What
Added the `knowledge_auto_sync` editable preference (bool, default seeded from
`settings.knowledge_auto_sync`) plus `Settings` fields
`knowledge_auto_sync`, `knowledge_sync_interval_seconds` (30),
`gdrive_sync_interval_seconds` (300).

## Why
Runtime on/off control + cadence for the background auto-sync loop (Phase B).

## Files touched
- `services/assistant-core/src/violet_assistant/preferences/store.py`
- `services/assistant-core/src/violet_assistant/config.py`
- `services/assistant-core/tests/test_preferences.py`

## Interfaces / contracts changed
- New pref `knowledge_auto_sync`; env `KNOWLEDGE_AUTO_SYNC`,
  `KNOWLEDGE_SYNC_INTERVAL_SECONDS`, `GDRIVE_SYNC_INTERVAL_SECONDS`.

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_preferences.py -q` → 8 passed.

## Next
Task 2: AutoSyncScheduler.
