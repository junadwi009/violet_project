# Runtime preferences store + /api/settings

- **Date:** 2026-07-25
- **Track:** cross-cutting (Track 1 Chat)
- **Branch:** feat/slash-canvas-settings-websearch
- **Author:** Claude (executing 2026-07-25 plan, Task 1)

## What
Added a JSON-backed `PreferencesStore` that layers runtime-editable UX/behavior
preferences over the frozen `Settings`, plus `GET/PATCH /api/settings`. Added
config fields for web search (`web_search_base_url/model/api_key`) and
`default_temperature`.

## Why
"Claude-like settings": model, temperature, memory-approval, web-search and
canvas toggles need to be editable at runtime and persisted, without exposing
secrets/infra (those stay in `.env`).

## Files touched
- `services/assistant-core/src/violet_assistant/preferences/__init__.py` (new)
- `services/assistant-core/src/violet_assistant/preferences/store.py` (new)
- `services/assistant-core/src/violet_assistant/routes/settings.py` (new)
- `services/assistant-core/src/violet_assistant/config.py` (new fields)
- `services/assistant-core/src/violet_assistant/main.py` (shared seam: build store, include router)
- `services/assistant-core/tests/test_preferences.py` (new)

## Interfaces / contracts changed
- New: `PreferencesStore.effective/patch/overridden/defaults`, `EDITABLE_KEYS`.
- New routes: `GET /api/settings`, `PATCH /api/settings` →
  `{values, defaults, overridden}`.
- New env vars: `WEB_SEARCH_BASE_URL`, `WEB_SEARCH_MODEL`, `WEB_SEARCH_API_KEY`,
  `DEFAULT_TEMPERATURE`. Persisted overrides live in `data/preferences.json`.

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_preferences.py -q` → 6 passed.
Full suite `python -m pytest -q` → 79 passed.

## Next
Task 2 wires `PreferencesStore` into `ChatOrchestrator` (effective temperature/
model) and adds explicit-skill + web-search routing.
