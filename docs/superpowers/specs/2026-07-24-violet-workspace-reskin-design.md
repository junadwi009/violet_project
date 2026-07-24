# Violet Workspace Re-skin — Design Spec

**Date:** 2026-07-24
**Status:** Approved (user chose "do your recommendation; wire everything functional, nothing read-only")
**Source mockup:** `violet_project_assistant.html` (visual reference only — not shipped)

## Goal
Re-skin `apps/web-client` (React 19 + Vite) to the premium light-amethyst "Violet Workspace"
design, keeping every backend contract, the memory-approval feature, and all six track seams.
Every interactive element is **functional** — no read-only placeholders, no dead buttons.

## Decisions (from brainstorming)
1. **Strategy:** re-skin the existing React client (not replace with the HTML, not a new app).
2. **Styling:** adopt Tailwind v4 via `@tailwindcss/vite`; vendor Inter + JetBrains Mono via
   `@fontsource/*`; keep `lucide-react` for icons (map FontAwesome → lucide). No CDNs (local-first).
3. **Memory:** right slide-out drawer, toggled from the floating tool pill, with a pending-count badge.
4. **Naming:** assistant is **Violet** everywhere (drop "Lina").
5. **Scope wired:** New chat, Recents, Search, Settings (persona + provider), Voice overlay.
   Dropped: Images / Videos / Library.
6. **Provider pill is a real switch** (user override of the read-only recommendation).
7. **Theme:** light amethyst palette this slice; colors are tokens so a dark variant is possible later.

## Backend additions (assistant-core)
- **Runtime provider switch.** `llm/registry.py::build_provider_registry(settings)` → `{name: LLMProvider}`
  exposing at least `mock` and `openai_compatible` (built from `LLM_BASE_URL`/`LLM_API_KEY`).
  `GET /api/providers` → `{items:[{id,label,active}], active}`. `ChatRequest` gains optional `provider`.
  `ChatOrchestrator` gains an optional `provider_registry`; per request it uses
  `registry[request.provider]` when present, else the default `provider`. Backward compatible.
- **Sessions.** `store.list_sessions()` and `store.messages_for_session(id)`.
  `GET /api/sessions` (id, title, updated_at, message_count) and
  `GET /api/sessions/{id}/messages` (full history, ascending) for Recents + reload.
  "Search chats" = client-side filter over the session list this slice (server full-text later).
- Tests: `test_providers.py`, `test_sessions.py` (pytest, matching existing style).

## Frontend structure (`apps/web-client/src/`)
- `index.css` — Tailwind import + `@theme` tokens (navy/steel palette), fonts, custom utilities
  (glass panel, soft-edge avatar mask, glow animation, violet scrollbar).
- `components/`: `Sidebar`, `WorkspaceHeader`, `EmptyState`, `ChatTimeline` (+ `MessageBubble`,
  `TypingIndicator`), `Composer`, `AvatarPresence` (Track 4 VRM mount point), `VoiceOverlay`
  (Track 5/6 home), `FloatingTools`, `MemoryDrawer` (wraps existing candidate/approved cards),
  `SettingsModal`, `HelpModal`.
- `App.tsx` keeps its state machine + handlers; renders the new shell.
- `lib/api.ts` extended: `fetchProviders`, `sendChat(…, provider)`, `fetchSessions`, `fetchSessionMessages`.
- `lib/speech.ts`, `lib/avatar.ts` unchanged.

## Track mount points (kept explicit)
- `AvatarPresence` renders the 2D portrait now; structured so Track 4 swaps a three.js/VRM `<canvas>`
  without layout changes. Consumes existing `AvatarState`/`AvatarEmotion`.
- `VoiceOverlay` is the visual home Track 5/6 wire real STT/TTS into (browser Web Speech today).

## Testing / gate
- Backend: `python -m pytest` green (adds provider + sessions tests).
- Frontend: `tsc -b && vite build` clean (repo has no FE test runner; adding Vitest is a later decision).

## Slices (each = its own `logs/{update}_{date}_log.md` per the CLAUDE.md rule)
1. Foundation — Tailwind + Vite plugin, fonts, palette tokens, icon mapping.
2. Shell & theme — sidebar, header, empty state, composer, chat timeline; New chat.
3. Memory drawer — existing cards into the slide-out + floating-tools toggle + badge.
4. Avatar + Voice — floating portrait slot + voice overlay (Web Speech).
5. Settings + Help — real persona selector, **live provider switch**, palette, rewritten help.
6. Recents/Search — backend session endpoints, sidebar Recents, client-side search.

## Out of scope
Real STT/TTS models, VRM rendering, dark theme, server-side full-text search, FE test runner.
