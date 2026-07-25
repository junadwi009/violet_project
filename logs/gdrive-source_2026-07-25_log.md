# GoogleDriveSource (recursive, shared drive, export/download)

- **Date:** 2026-07-25
- **Track:** 2 RAG
- **Branch:** feat/gdrive-connector
- **Author:** Claude (executing gdrive plan, Task 4)

## What
`GoogleDriveSource` implements `KnowledgeSource` (`name="gdrive"`): recursive
folder listing (Shared-Drive aware via `supportsAllDrives`/
`includeItemsFromAllDrives` + optional `corpora=drive,driveId`), mime→extension
mapping, native export (Docs→md, Sheets→csv, Slides→txt) vs binary download,
version = md5Checksum else modifiedTime, unique `display_path` (id suffix). The
Drive `service` is injectable for tests; real client + creds are lazy-imported.

## Why
The Google Drive knowledge source (Phase C core).

## Files touched
- `services/assistant-core/src/violet_assistant/knowledge/sources/google_drive.py` (new)
- `services/assistant-core/tests/test_gdrive_source.py` (new — fake Drive client, no network/libs)

## Interfaces / contracts changed
- New: `GoogleDriveSource(settings, service=None)`.

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_gdrive_source.py -q` → 4 passed
(incl. an end-to-end index-through-pipeline test; no google libs imported).

## Next
Task 5: config, dependency extra, `.env.example`, main wiring.
