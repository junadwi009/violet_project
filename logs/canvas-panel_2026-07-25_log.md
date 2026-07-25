# Frontend: canvas side panel + citations rendering

- **Date:** 2026-07-25
- **Track:** 1 Chat (web-client)
- **Branch:** feat/slash-canvas-settings-websearch
- **Author:** Claude (executing 2026-07-25 plan, Task 5 + folded Task 7 UI)

## What
`ArtifactView` sub-renderers (`ChartArtifact`/`HtmlArtifact`/`FileArtifact`) are
now exported and `ArtifactView` gained a `compact` mode (clickable "Open in
canvas" card). New `CanvasPanel` renders the active artifact large with a gallery
strip of all session artifacts; it is a right-hand panel on desktop and a
full-screen overlay below `lg`. `ChatTimeline` renders compact cards when an
`onOpenArtifact` handler is provided, and also renders web-search citations
under assistant messages (Task 7 UI, folded in since it is the same file).

## Why
Feature 3 (Canvas mode like Claude Artifacts / Gemini Canvas). Gated by the
`canvas_enabled` preference — when off, artifacts still render inline as before.

## Files touched
- `apps/web-client/src/components/ArtifactView.tsx` (export renderers + compact)
- `apps/web-client/src/components/CanvasPanel.tsx` (new)
- `apps/web-client/src/components/ChatTimeline.tsx` (SHARED SEAM: compact cards + citations)
- `apps/web-client/src/App.tsx` (SHARED SEAM: canvas state, session artifacts, layout)

## Interfaces / contracts changed
- `ArtifactView` props: `compact?`, `onOpen?`.
- `CanvasPanel({artifacts, activeId, onSelect, onClose})`.
- `ChatTimeline` prop: `onOpenArtifact?`.

## Status
done

## Verification
`npm run build` → built clean.

## Next
Task 6: expanded Settings modal (skills list + preference controls). Task 7
backend citations already wired in Task 2; message-level citation storage in
Task 4; UI rendering done here — Task 7 reduces to final verification.
