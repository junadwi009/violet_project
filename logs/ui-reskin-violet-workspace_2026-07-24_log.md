# UI Re-skin — Violet Workspace (premium light-amethyst)

- **Date:** 2026-07-24
- **Track:** UI track (parallel to backend Tracks 1–6) + small assistant-core additions
- **Branch:** codex/phase-1-text-mvp
- **Author:** Claude Code

## What
Re-skinned `apps/web-client` to the premium "Violet Workspace" design from
`violet_project_assistant.html`, ported into React + Tailwind v4. Every interactive element is
functional (no read-only placeholders). Added the backend needed to make the provider switch
and Recents/Search real.

## Why
Adopt the mockup's look while keeping the backend, memory-approval feature, and the six track
seams. Design spec: `docs/superpowers/specs/2026-07-24-violet-workspace-reskin-design.md`.

## Backend additions (assistant-core)
- **Runtime provider switch:** `llm/registry.py` (`build_provider_registry`, `default_provider_name`,
  `describe_providers`); `GET /api/providers`; `ChatRequest.provider`; `ChatOrchestrator`
  `provider_registry` + `_select_provider` (falls back to default on unknown). Backward compatible.
- **Sessions:** `store.list_sessions()`, `store.messages_for_session()`; `GET /api/sessions`,
  `GET /api/sessions/{id}/messages` (`routes/sessions.py`). Wired in `main.py`.
- Tests: `tests/test_providers_and_sessions.py` (registry, active-marking, provider selection,
  unknown-provider fallback, session list + message reload).

## Frontend
- Build: added `tailwindcss` + `@tailwindcss/vite` (Vite plugin, not CDN); vendored fonts via
  `@fontsource/inter` + `@fontsource/jetbrains-mono`; kept `lucide-react` (FontAwesome → lucide).
  `vite.config.ts` + new `src/index.css` (Tailwind `@theme` tokens, glass/glow/soft-edge utilities).
- New components: `Sidebar`, `WorkspaceHeader`, `EmptyState`, `ChatTimeline`, `Composer`,
  `AvatarPresence` (Track 4 VRM mount point), `VoiceOverlay` (Track 5/6 home), `FloatingTools`,
  `MemoryDrawer`, `SettingsModal`, `HelpModal`. `App.tsx` rewritten as the shell/orchestrator.
- `lib/api.ts`: `fetchProviders`, `fetchSessions`, `fetchSessionMessages`, `sendChat(...,provider)`.
- Removed dead files: `components/AvatarPanel.tsx`, `styles.css`.
- Naming: assistant is **Violet** everywhere. Dropped Images/Videos/Library (YAGNI).

## Interfaces / contracts changed
- `ChatRequest` gained optional `provider`. New `GET /api/providers`, `GET /api/sessions`,
  `GET /api/sessions/{id}/messages`. `ChatOrchestrator` gained optional `provider_registry`
  (backward compatible). No breaking changes to existing endpoints.

## Status
done — builds clean, tests green, live-verified.

## Verification
- Backend: `python -m pytest` → **26 passed** (+6 provider/session tests).
- Frontend: `npm run build` (`tsc -b && vite build`) → clean, fonts emitted locally.
- Live: uvicorn on :8000 + vite on :5173. `GET /health`, `/api/providers`, `/api/personalities`
  all 200. `POST /api/chat {"provider":"mock"}` returned the mock response + extracted a memory
  candidate — proving the runtime provider switch. Rendered DOM shows the full shell (sidebar,
  empty state, composer with engine pill, floating tools, avatar presence, memory drawer with
  live "2 pending · 1 approved" data). Zero console errors.

## Next / open for user insight
- Provider pill defaults to the **server's** active provider (`openai_compatible` in the local
  `.env`); user switches to Mock in Settings. Confirm that default is what you want.
- Track 4 swaps `AvatarPresence`'s gradient orb for a VRM `<canvas>`.
- Dark theme, server-side full-text search, and a FE test runner remain out of scope.
