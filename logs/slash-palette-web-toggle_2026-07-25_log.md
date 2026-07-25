# Frontend: slash skill palette + web-search toggle

- **Date:** 2026-07-25
- **Track:** 1 Chat (web-client)
- **Branch:** feat/slash-canvas-settings-websearch
- **Author:** Claude (executing 2026-07-25 plan, Task 4)

## What
`lib/api.ts` gains `skillId`/`webSearch` options on `sendChat`, `citations` on
`ChatResponse`/`ChatMessage`, and `fetchSettings`/`patchSettings`/`fetchUrl` +
`AppSettings`/`FetchResult` types. New `SkillPalette` opens when the composer
draft starts with `/`; picking a skill sets a one-shot chip whose id rides on the
next send. A globe toggle (shown only when `web_search_enabled`) flips web mode.

## Why
Feature 1 (explicit `/slash` invocation) and Feature 4 UI surface.

## Files touched
- `apps/web-client/src/lib/api.ts`
- `apps/web-client/src/components/SkillPalette.tsx` (new)
- `apps/web-client/src/components/Composer.tsx` (SHARED SEAM: composer)
- `apps/web-client/src/App.tsx` (SHARED SEAM: state, mount load, send opts)

## Interfaces / contracts changed
- `sendChat(..., opts?: {skillId?, webSearch?})`.
- New API helpers `fetchSettings`, `patchSettings`, `fetchUrl`.
- Composer props: `activeSkill`, `onPickSkill`, `webSearchAvailable`,
  `webSearchOn`, `onToggleWebSearch`.

## Status
done (settings modal wiring of `skills`/`handlePatchSettings` lands in Task 6)

## Verification
`npm run build` → built clean (tsc + vite).

## Next
Task 5: canvas side panel.
