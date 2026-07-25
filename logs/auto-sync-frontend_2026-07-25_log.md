# Frontend: auto-sync toggle + last-sync display

- **Date:** 2026-07-25
- **Track:** 1 Chat (web-client)
- **Branch:** feat/knowledge-auto-sync
- **Author:** Claude (executing Phase B plan, Task 4)

## What
`KnowledgeInfo` gains `auto_sync` (`AutoSyncInfo`). The Settings Knowledge card
adds an **Auto-sync** toggle bound to the `knowledge_auto_sync` preference (live
state from `settings.values`, so it flips without re-fetching), and each source
row shows its last-sync time from `auto_sync.last_sync`.

## Why
Feature: Phase B auto-sync UX — turn it on/off and see when each source last
synced.

## Files touched
- `apps/web-client/src/lib/api.ts`
- `apps/web-client/src/components/SettingsModal.tsx`

## Interfaces / contracts changed
- `KnowledgeInfo.auto_sync: AutoSyncInfo`.

## Status
done

## Verification
`cd apps/web-client && npm run build` → built clean.

## Next
Final verification + finish branch.
