# Settings: Data & privacy panel (export + clear all sessions)

- **Date:** 2026-07-28
- **Track:** 1 Chat (cross-cutting UI — settings dialog)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code (Task 15 of the settings overhaul plan)

## What

Added the final settings panel, `DataPanel` ("Data & privacy"). It does three things:

1. **Backup** — downloads the export bundle from `GET /api/export` via `downloadExport()`.
2. **Safety configuration** — renders the 8-key read-only `locked` block from `GET /api/settings` as status text.
3. **Danger zone** — clears every session/message behind an inline typed confirmation.

Also added `--color-danger` to the semantic status tokens in `index.css`, and wired
`handleDeleteAllSessions` in `App.tsx`.

## Why

Phase B built the backend for export and bulk session deletion; nothing in the UI reached
either. This panel is the only entry point for both, and it holds the plan's only
destructive action.

Three decisions worth recording:

**Export errors are branched, not collapsed.** `downloadExport()` deliberately does not
throw — it returns a discriminated `ExportOutcome`. The three interesting failures have
completely different fixes:

| kind | what is wrong | fix |
|---|---|---|
| `client_token_missing` | `VITE_VIOLET_API_TOKEN` unset in the browser build | set it client-side + restart Vite |
| `server_not_configured` | server has no `VIOLET_API_TOKEN`; endpoint returns 503 | set it server-side + restart the API |
| `unauthorized` | both sides have a token and they disagree | make them match + restart Vite |

Rendering "export failed" for all three would tell a user nothing. `http_error` and
`network_error` are also handled.

**No dead download control.** `client_token_missing` is knowable at render time (the fetch
short-circuits), so in that state the button is not rendered at all — the explanation takes
its place. Same after a 503: the control is removed, because no click could succeed.
`unauthorized` keeps the button (a token can be fixed and retried).

**Export availability feeds the danger zone.** The stated justification for offering
"clear all sessions" is that export is the backup path. When export is unavailable the
danger zone says so explicitly instead of letting the section imply a backup exists.

**The confirmation is inline, not a nested dialog.** `SettingsShell` handles Escape in the
*capture* phase, so it would pre-empt a nested dialog's own Escape handler and close the
whole Settings dialog out from under it. Building the confirmation into the panel body
means there is nothing to nest and Escape keeps one meaning.

**`DataPanel` does not take `PanelProps`.** It writes no preferences, so `values` /
`overridden` / `patchNow` / `patchDebounced` would all be dead props. It receives `locked`
and `onDeleteAllSessions` only.

## Files touched

- `apps/web-client/src/components/settings/panels/DataPanel.tsx` — **new**
- `apps/web-client/src/components/settings/SettingsPanel.tsx` — import + `case "data"`;
  `onDeleteAllSessions` promoted from optional placeholder to required
  `() => Promise<void>`
- `apps/web-client/src/App.tsx` — `handleDeleteAllSessions`, `deleteAllSessions` import,
  prop wiring
- `apps/web-client/src/index.css` — **shared seam**: added `--color-danger` to the
  semantic status block (light `#b91c1c`, dark `#f87171`), with the measured contrast
  numbers recorded in a comment

## Interfaces / contracts changed

- `SettingsPanelProps.onDeleteAllSessions` is now **required** and returns a promise
  (`() => Promise<void>`); it was previously `onDeleteAllSessions?: () => void`, a
  placeholder left by Task 5. `App.tsx` is the only caller.
- New CSS custom property `--color-danger` (both themes).
- No backend change, no new env var. `VITE_VIOLET_API_TOKEN` / `VIOLET_API_TOKEN` were
  already introduced by the export-auth task.

## Status

done

## Verification

**Build** — `cd apps/web-client && npm run build` → `tsc -b && vite build`, `✓ built in
12.65s`, no errors.

**Browser** — Chrome against Vite `127.0.0.1:5173` + `uvicorn 127.0.0.1:8000` with
`LLM_PROVIDER=mock`. Token values used for testing were set in the shell only; the real
`.env` was neither read nor modified.

| Check | Result |
|---|---|
| `client_token_missing` (Vite started with no `VITE_VIOLET_API_TOKEN`) | No download button in the DOM at all — only the explanation. Danger zone showed "Export is unavailable, so there is no backup to fall back on." |
| `unauthorized` (Vite with `deliberately-wrong-token`, server with the real one) | 401 → `role="alert"`: "Export was rejected… Make VITE_VIOLET_API_TOKEN identical to the server's VIOLET_API_TOKEN…". Button stayed available for retry. |
| `server_not_configured` (server restarted with `VIOLET_API_TOKEN=`) | 503 → download control **removed**, "Export is disabled on the server… No change in the browser will help." Danger zone flipped back to the no-backup copy. |
| Success (both tokens matching) | "Downloaded violet-export-20260727-193948.json" — filename came from `Content-Disposition`, confirming the CORS expose-header fix works cross-origin. |
| Export file contents | 41 818 bytes on disk. `sessions: 30`, `messages: 111`, `memories: 2`, `preferences.overridden: [ui_mode, theme]`. Zero occurrences of `api_key`, `base_url`, `password`, `token`, `secret`. Top-level keys contain no `locked` block. |
| Safety block | All 8 flags rendered with friendly labels; the section contains **0** buttons/inputs/links. No key, URL, or path shown. |
| Typed confirmation | `delet` → disabled. `Delete` (wrong case) → disabled. `Deletedeletdelete…` → disabled. `delete` → enabled. |
| Clear all sessions | API 30 → 0 sessions; memory candidates 2 → 0; approved memories preserved at 2. Sidebar emptied to "No conversations yet"; chat reset to the empty state with header "New session"; status bar read "Cleared 30 sessions, 111 messages"; the confirmation input reset itself. |
| Memory drawer after clear | "0 pending · 2 approved" / "No pending candidates" — the orphaned candidates are gone, which is why `refreshMemory()` is in the handler. |
| Escape with the confirmation input focused | Closes the whole Settings dialog. Confirms the capture-phase behaviour and that nothing nests. |
| Console | No errors and no warnings for the whole session. |

**Contrast (measured in-page, canvas-resolved sRGB, not eyeballed)** — every string this
panel introduces clears WCAG AA 4.5:1 in **both** themes. The enabled "Clear all sessions"
label measures 5.95:1 light / 5.44:1 dark.

An earlier revision filled the button with `bg-danger/15`; stacked on the section's own
`/5` tint that measured **4.29:1 in dark**, under AA. Changed to a transparent resting
fill with the tint on hover only. No `bg-steel-dark text-white` or `bg-white` +
`text-steel-dark` pairing was introduced anywhere, so Task 17's inventory does not grow.

The one sub-AA string in the panel (`SectionHeader`'s description, `text-steel/70`,
4.42:1 dark) belongs to a shared control used by every panel and predates this task —
left for Task 17.

## Next

- Task 16 integration, Task 17 the dark-mode contrast sweep.
- The dev SQLite database was genuinely emptied by the clear test (30 sessions of prior
  tasks' scratch conversations). Pre-clear copies exist as the exported JSON in the user's
  Downloads folder and a `violet.db` snapshot in this session's scratchpad, if anyone
  wants them back; otherwise both can be deleted.
