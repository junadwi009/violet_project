# Frontend: Knowledge section + user/developer mode gating

- **Date:** 2026-07-25
- **Track:** 1 Chat (web-client)
- **Branch:** feat/knowledge-base-and-ui-modes
- **Author:** Claude (executing knowledge-base plan, Task 8)

## What
`lib/api.ts` gains `KnowledgeInfo`/`KnowledgeDoc`/`ReindexReport` types +
`fetchKnowledge`/`reindexKnowledge`. Settings modal gets a **Knowledge base**
section (path, doc/chunk counts, Reindex; Full rebuild + doc list are
developer-only) and a **Mode** switch (`user | developer`) at the top. Developer
mode reveals AI engine, routing cascade, agent delegation, temperature, the
web-search model field, the Palette block, the Open-Skill-Lab button, and the
knowledge doc list; user mode keeps persona, simple toggles, and Reindex.
`FloatingTools` hides the Skill Lab button in user mode.

## Why
Feature: local knowledge base UX + the requested User/Developer mode mapping.

## Files touched
- `apps/web-client/src/lib/api.ts`
- `apps/web-client/src/components/SettingsModal.tsx` (SHARED SEAM: settings)
- `apps/web-client/src/components/FloatingTools.tsx`
- `apps/web-client/src/App.tsx` (SHARED SEAM: state + wiring)

## Interfaces / contracts changed
- New API helpers `fetchKnowledge`, `reindexKnowledge`.
- `SettingsModalProps`: `knowledge`, `onReindex`, `devMode`.
- `FloatingToolsProps`: `devMode`.

## Status
done

## Verification
`cd apps/web-client && npm run build` → built clean (tsc + vite).

## Next
Final verification + finish branch.
