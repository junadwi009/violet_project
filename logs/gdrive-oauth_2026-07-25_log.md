# Google Drive OAuth helper (installed-app flow)

- **Date:** 2026-07-25
- **Track:** 2 RAG
- **Branch:** feat/gdrive-connector
- **Author:** Claude (executing gdrive plan, Task 3)

## What
`knowledge/gdrive_auth.py`: `is_authorized`, `load_credentials` (lazy-imports
google libs; returns None with no token file — no import needed), `authorize`
(interactive `InstalledAppFlow.run_local_server`, opens local browser),
`revoke`, and a `python -m` CLI. Scope: `drive.readonly`. Token stored at
`GDRIVE_TOKEN_PATH` (default `data/gdrive_token.json`, gitignored via `data/`).

## Why
One-time OAuth consent for the read-only Drive connector, local-first.

## Files touched
- `services/assistant-core/src/violet_assistant/knowledge/gdrive_auth.py` (new)
- `services/assistant-core/tests/test_gdrive_auth.py` (new)

## Interfaces / contracts changed
- New: `gdrive_auth.{token_path,is_authorized,load_credentials,authorize,revoke}`.

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_gdrive_auth.py -q` → 2 passed
(no google libraries imported).

## Next
Task 4: GoogleDriveSource.
