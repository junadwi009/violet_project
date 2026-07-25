# ui_mode preference (user/developer)

- **Date:** 2026-07-25
- **Track:** cross-cutting
- **Branch:** feat/knowledge-base-and-ui-modes
- **Author:** Claude (executing knowledge-base plan, Task 7)

## What
Added `ui_mode` (values `user`/`developer`, default `user`) to the preferences
`EDITABLE_KEYS`, persisted + exposed via `/api/settings`.

## Why
Backing store for the User/Developer UI mode that filters which controls the
frontend shows.

## Files touched
- `services/assistant-core/src/violet_assistant/preferences/store.py`
- `services/assistant-core/tests/test_preferences.py`

## Interfaces / contracts changed
- New editable preference key `ui_mode`.

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_preferences.py -q` → 7 passed.

## Next
Task 8: frontend knowledge section + mode switch + gating.
