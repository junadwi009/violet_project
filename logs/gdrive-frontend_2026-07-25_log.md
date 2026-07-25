# Frontend: knowledge sources UI + Google Drive connect

- **Date:** 2026-07-25
- **Track:** 1 Chat (web-client)
- **Branch:** feat/gdrive-connector
- **Author:** Claude (executing gdrive plan, Task 7)

## What
`lib/api.ts` gains `SourceStatus`, `sources` on `KnowledgeInfo`, a `source` arg on
`reindexKnowledge`, and `connectGDrive`/`disconnectGDrive`. The Settings Knowledge
section now lists each source with connection state: Google Drive shows
**Connect** (runs OAuth) when unauthorized-but-configured, and **Sync** +
(developer mode) **Disconnect** when connected. `App` wires connect/disconnect/
per-source reindex handlers.

## Why
Feature: Google Drive connector UX (Phase C) — connect, see status, sync.

## Files touched
- `apps/web-client/src/lib/api.ts`
- `apps/web-client/src/components/SettingsModal.tsx` (SHARED SEAM: settings)
- `apps/web-client/src/App.tsx` (SHARED SEAM: handlers + wiring)

## Interfaces / contracts changed
- `reindexKnowledge(full, source?)`; `connectGDrive`/`disconnectGDrive`.
- `SettingsModalProps`: `onConnectGDrive`, `onDisconnectGDrive`; `onReindex(full, source?)`.

## Status
done

## Verification
`cd apps/web-client && npm run build` → built clean.

## Next
Final verification + finish branch.
