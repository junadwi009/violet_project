# Google Drive config + optional drive extra + source wiring

- **Date:** 2026-07-25
- **Track:** 2 RAG / cross-cutting
- **Branch:** feat/gdrive-connector
- **Author:** Claude (executing gdrive plan, Task 5)

## What
Confirmed the gdrive `Settings` fields + `KNOWLEDGE_SOURCES` (added in Task 2)
read from env; `main.py` appends `GoogleDriveSource` when `gdrive` is enabled and
configured (lazy import, so core boots without google libs). Added a `drive`
optional dependency extra and documented the Phase A/C env vars in `.env.example`
(names only).

## Why
Make the Drive source installable and configurable without touching core deps.

## Files touched
- `services/assistant-core/tests/test_config_gdrive.py` (new)
- `pyproject.toml` (`drive` extra)
- `.env.example` (knowledge + gdrive vars)

## Interfaces / contracts changed
- `pip install -e ".[drive]"` installs `google-api-python-client`, `google-auth`,
  `google-auth-oauthlib`.

## Status
done

## Verification
`python -m pytest -q` → 127 passed. App boots with Drive off by default (no
google libs imported).

## Next
Task 6: knowledge routes (per-source status + gdrive connect/status/disconnect).
