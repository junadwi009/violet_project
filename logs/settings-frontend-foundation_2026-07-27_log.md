# Settings overhaul — frontend foundation (Phase C: Tasks 8-10)

- **Date:** 2026-07-27
- **Track:** cross-cutting (settings overhaul, Phase C of an 18-task plan)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code

## What

Phase C built the three pieces the new settings UI (Phase D onward) will be assembled
from, without touching the app's actual behavior:

- **Task 8** — extended `apps/web-client/src/lib/api.ts` with the settings-reset,
  session-delete, and export-download API client functions the new panels need.
- **Task 9** — added dark-theme/accent/density/font-scale CSS tokens and a
  `src/lib/theme.ts` helper module, plus a pre-paint script so a dark-theme user doesn't
  flash light on load.
- **Task 10** — built the settings shell skeleton: a `SettingsShell` modal frame with a
  `SettingsNav` tab rail, five shared control components, and a `useDebouncedPatch` hook.

None of this is wired into the running app yet. The existing `SettingsModal.tsx` is
untouched and still in use; Task 11 assembles the new panels and swaps it in.

## Why

The old settings modal is a single 500-line file covering ten unrelated concerns
(general, appearance, model, behavior, voice, knowledge, sessions, export, dev tools).
The plan splits it into a shell + per-concern panels. Phase C's job was to land the
non-visible groundwork — API surface, theme machinery, shared UI primitives — so Phase D
panels can be built and reviewed independently without also re-litigating shell layout,
accessibility, or debounce behavior each time.

## Files touched

### Task 8
- `apps/web-client/src/lib/api.ts` — `SettingsValues` extracted as its own type;
  `AppSettings.locked` field added; `SettingsGroup` union; `resetSettings()`;
  `DeleteReport` type, `deleteSession()`, `deleteAllSessions()`; `downloadExport()`
  (see deviation below).
- `.env.example` (repo root) — added `VITE_VIOLET_API_TOKEN=` under the existing
  "Web client" section (`apps/web-client/.env.example` does not exist, so the root file
  is where this belongs, consistent with how `VIOLET_API_TOKEN` is already documented
  there).

### Task 9
- `apps/web-client/src/index.css` — `[data-theme="dark"]` token overrides,
  `--color-success` / `--color-warning`, four `[data-accent="…"]` hues (x2 for dark),
  `--font-scale` on `html`, `--row-pad` density variable.
- `apps/web-client/src/lib/theme.ts` — new. Exports `Appearance`, `ThemeChoice`,
  `DensityChoice`, `AccentChoice`, `DEFAULT_APPEARANCE`, `applyAppearance()`,
  `appearanceFromSettings()`, `readCachedAppearance()`, `writeCachedAppearance()`,
  `watchSystemTheme()`, `clampFontScale()` (added in the fix pass).
- `apps/web-client/index.html` — synchronous pre-paint script in `<head>`.

### Task 10
- `apps/web-client/src/components/settings/useDebouncedPatch.ts` — new.
- `apps/web-client/src/components/settings/SettingsNav.tsx` — new.
- `apps/web-client/src/components/settings/SettingsShell.tsx` — new. Exports
  `PanelProps` and `SettingsShell`.
- `apps/web-client/src/components/settings/controls/ToggleRow.tsx` — new.
- `apps/web-client/src/components/settings/controls/SegmentedRow.tsx` — new
  (one deviation from the brief's sample code — see below).
- `apps/web-client/src/components/settings/controls/SliderRow.tsx` — new.
- `apps/web-client/src/components/settings/controls/TextRow.tsx` — new.
- `apps/web-client/src/components/settings/controls/SectionHeader.tsx` — new.

No backend code touched in any of the three tasks. No new dependencies added
(`lucide-react` was already a dependency, used for icons in `SectionHeader` and
`SettingsShell`). No test framework added — the frontend has none and this plan does
not add one.

## Interfaces / contracts changed

- `apps/web-client/src/lib/api.ts` now exports `SettingsValues`, `AppSettings`
  (with `locked`), `SettingsGroup`, `resetSettings`, `DeleteReport`,
  `deleteSession`, `deleteAllSessions`, `ExportError`, `ExportOutcome`,
  `downloadExport`.
- `apps/web-client/src/lib/theme.ts` (new module, no consumers yet). New DOM contract:
  `<html data-theme data-density data-accent style="--font-scale">`. New `localStorage`
  key `violet.appearance` (paint hint only; server value overwrites on load).
- `apps/web-client/src/components/settings/SettingsShell.tsx` (new module, no consumers
  yet) exports `PanelProps` — the props shape Tasks 11-15 build panels against — and
  `SettingsShell`.
- No env vars added by Task 9 or 10. Task 8 documents `VITE_VIOLET_API_TOKEN` (already
  consumed by `downloadExport`, not new to this phase's wiring — the client-side
  gate for the existing `VIOLET_API_TOKEN` server env var).

## Deviations from the briefs

1. **Task 8 — `exportUrl(): string` replaced with `downloadExport(): Promise<ExportOutcome>`.**
   `GET /api/export` is gated behind a bearer token, so a bare URL (the brief's original
   shape) cannot carry the `Authorization` header a plain anchor-tag download needs. The
   401 (client token wrong/missing) vs 503 (server has no token configured at all) cases
   also need to be distinguishable by callers without string-matching an error message,
   so `downloadExport()` returns a discriminated union
   (`ExportOutcome = { ok: true; filename } | { ok: false; error: ExportError }`,
   `ExportError` one of `client_token_missing | server_not_configured | unauthorized |
   http_error | network_error`) instead of throwing. On success it fetches the blob,
   parses `Content-Disposition` for the real filename, and drives a programmatic
   `<a download>` click.

2. **Task 9 fix pass — three corrections after the initial implementation, all found and
   fixed same-day, before this phase closed:**
   - `font-size: calc(16px * var(--font-scale))` was changed to
     `calc(1rem * var(--font-scale))` — `rem` on the root resolves against the browser's
     own default font size, so a user who changed their browser default keeps it instead
     of the app silently overriding it to a hardcoded 16px baseline.
   - `--font-scale` had no validation anywhere it could enter (a hand-edited
     `preferences.json`, or `localStorage` written outside the app). `NaN`, `0`, or a
     negative value all collapse `html { font-size: 0px }` — a valid, not an invalid,
     calc token — which zeroes every rem-based utility in the app, including the panel
     that would let a user undo it. Added `clampFontScale()` in `lib/theme.ts`, applied
     in `appearanceFromSettings` and `readCachedAppearance`, and mirrored inline in the
     pre-paint script (which runs before the bundle and can't import it).
   - Two accent hues failed WCAG AA as text against their surfaces: light teal `#0d9488`
     measured 3.44:1 (now `#0f766e`, 5.02:1) and the default dark violet `#a855f7`
     measured 4.10:1 on cards (now `#c084fc`, 6.14:1). All ten theme×accent combinations
     now clear 4.5:1 against both the page and card surface tokens.
   - A documentation correction: an earlier draft of the Task 9 report claimed opacity
     modifiers (`bg-navy-900/60` etc.) compile to literal colors and can't follow the
     theme token — this was wrong (Tailwind v4 emits a `color-mix()` override behind an
     `@supports` block that resolves the CSS variable live), and was corrected before
     handoff so Task 17 isn't sent to rewrite call sites that don't need it.

3. **Task 10 — `SegmentedRow`'s selected-option style changed from the brief's
   `bg-steel-dark text-white` to `bg-steel-highlight/15 text-steel-highlight`.**
   Task 9's dark-mode tokens make `--color-steel-dark` near-white
   (`#f2ecfa`), so `bg-steel-dark text-white` renders white text on a white fill —
   measured elsewhere in this codebase at 1.16:1 contrast, i.e. invisible, not just hard
   to read. The Task 9 report explicitly flags this exact pairing as a known, blocking,
   not-yet-fixed defect (13 existing call sites, to be swept in Task 17) and this task's
   own instructions said not to add another one. The replacement mirrors the pattern
   `SettingsNav`'s active-tab state already uses in the same brief
   (`bg-steel-highlight/10 text-steel-highlight`), which is safe: the theme-tokens log
   already verified every accent hue clears 4.5:1 against both surface tokens as *text*,
   and a translucent tint of that same color as a background doesn't change that.
   `SettingsShell`'s backdrop (`bg-steel-dark/30`) was left as specified — it's a scrim,
   not a text/background pairing, so the white-on-white failure mode doesn't apply to
   it; the Task 9 report separately flags scrims as a cosmetic (wrong-direction, not
   unreadable) issue for Task 17, out of scope here.

## Status

Done. Nothing in Phase D imports any of this yet — Task 11 is the first consumer of the
Task 10 shell/nav/controls, Task 12 and Task 16 are the first consumers of Task 9's
`theme.ts`, and Task 15 is the first consumer of Task 8's `downloadExport`.

## Verification

- **Task 8:** `cd apps/web-client && npm run build` → PASS, `tsc -b` strict + `vite
  build`, `✓ built in 31.12s`, 0 TS errors.
- **Task 9 (initial):** `npm run build` → PASS, `✓ built in 9.20s`. Runtime: pre-paint
  script confirmed stamping `theme/density/accent/--font-scale` on `<html>` before React
  mounted; dark-mode inversion, all 10 theme×accent hex values, and density's `--row-pad`
  switch verified live against the backend on :8000 and Vite on :5173.
- **Task 9 (fix pass):** `npm run build` → PASS, `✓ built in 14.30s`. All ten contrast
  ratios independently recomputed from the committed hex values via the WCAG
  relative-luminance formula against both surface tokens — worst case 4.61:1, all pass
  (light violet 6.52, indigo 5.77, teal 5.02, amber 4.61, rose 5.77; dark violet 6.14,
  indigo 5.44, teal 8.71, amber 9.71, rose 6.02). The two replaced values re-measured at
  their old, failing values (3.44, 4.10) to confirm the "before" state was real.
- **Task 10:** `npm run build` → PASS, `tsc -b` strict + `vite build`,
  `✓ built in 14.92s`, 0 TS errors. Nothing imports the new `settings/` directory yet,
  so this only confirms the new files themselves type-check and don't break the existing
  build.

  Keyboard/accessibility verified live in a browser (not by reading the code), using a
  temporary harness component (`SettingsShellHarness.tsx`, mounted in place of `<App/>`
  in `main.tsx` for the duration of the check, then deleted and `main.tsx` reverted
  before committing — confirmed via `git status` and a final rebuild that the tree is
  clean and `main.tsx` has no diff):
  - `role="dialog"`, `aria-modal="true"`, `aria-labelledby="settings-title"` present on
    open; opening the dialog moves focus to the active `role="tab"` element.
  - `role="tablist"` with `ArrowDown`/`ArrowUp` moving selection between tabs, including
    wraparound at both ends of the list (confirmed: from the first item, ArrowUp lands on
    the last; from the last, ArrowDown lands on the first), and the visible panel content
    updates in sync with the selected tab.
  - Focus trap: confirmed `Tab` from the last focusable element inside the dialog wraps
    to the first, and `Shift+Tab` from the first wraps to the last, **against two
    different panels with different focusable-element counts** (one panel with a single
    text field, another with four controls) — the wrap target changed correctly each
    time, confirming the trap re-queries focusable elements at keydown time rather than
    using a stale snapshot from when the dialog opened, which was the specific risk
    flagged for this task.
  - `Escape` closes the dialog.
  - Focus returns to the trigger button (`document.activeElement` was the "Open
    settings" button) after closing via `Escape`.

  One tool-level snag during verification, not a code issue: the browser automation
  tool's `key` action with a separate `modifiers: "shift"` parameter did not set
  `shiftKey` on the resulting event (confirmed by attaching a `keydown` listener and
  logging `e.shiftKey`); combining the modifier into the key string itself
  (`"shift+Tab"`) worked correctly. Documented here in case it trips up whoever verifies
  Task 11's assembled modal the same way.

## Next

Task 11 assembles `SettingsPanel.tsx` from this shell and swaps out the old
`SettingsModal.tsx`. Tasks 12-15 build the individual panels (Appearance, Model,
Behavior/Voice/Knowledge, Sessions/Export/Dev) against `PanelProps` and the control
components from Task 10, and against `theme.ts` from Task 9. Task 16 wires
`theme.ts`'s `applyAppearance`/`watchSystemTheme` into the running app. Task 17 is a
**gate**, not a follow-up: dark mode is not shippable until it sweeps the 13 existing
`bg-steel-dark text-white` call sites (white-on-white at 1.16:1, including the Composer
Send button and the old Settings modal's Done button) and the modal-scrim inversion —
both documented in the Task 9 report, neither touched by Phase C.
