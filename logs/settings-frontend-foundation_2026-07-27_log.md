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

### Backend

One backend change *was* required inside this phase, contrary to an earlier version of
this sentence which claimed none were. Commit `11549c2` modified
`services/assistant-core/src/violet_assistant/main.py` to expose `Content-Disposition`
to CORS clients on `/api/export`, and added `services/assistant-core/tests/test_cors.py`.
It was necessary *because of* Task 8: `downloadExport()` parses `Content-Disposition` for
the real filename, and a cross-origin browser client cannot read that header unless the
server lists it in `Access-Control-Expose-Headers`. Frontend-only work in this phase does
not otherwise touch backend code.

No new dependencies added
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
  - `role="tablist"` with `ArrowDown`/`ArrowUp` moving **selection** between tabs,
    including wraparound at both ends of the list (confirmed: from the first item,
    ArrowUp lands on the last; from the last, ArrowDown lands on the first), and the
    visible panel content updates in sync with the selected tab. **This check did not
    assert on `document.activeElement`, and as shipped DOM focus did *not* follow the
    selection** — see the Task 10 fix pass below.
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

---

# Addendum — Task 10 fix pass (2026-07-27)

## What

Applied nine code-review findings against the Task 10 shell/nav/controls. Accessibility
was the substantive requirement of Task 10 and is where most of them landed.

- **C1** `SettingsNav` arrow keys moved `aria-selected` but never DOM focus — no
  `.focus()` existed in the file. Added a tab-ref map and focus on every keyboard move,
  plus `Home`/`End` (required by the WAI-ARIA APG tablist pattern).
- **C2** `SettingsShell`'s focus effect was keyed `[open, onClose]` and its cleanup
  unconditionally returned focus to the trigger. With an inline-arrow `onClose` (which is
  what `App.tsx:700` passes) every parent render re-ran it, so saving a preference would
  have ripped focus out of whatever the user was typing in. `onClose` now lives in a ref;
  the effect depends on `[open]` alone.
- **I5** `useDebouncedPatch` degraded to a no-op: `flush` was `useCallback(…, [patch])`
  and `useEffect(() => flush, [flush])` therefore fired as a *render* cleanup whenever
  `patch` was unstable. `patch`/`delayMs` moved to refs, `flush` stable with `[]`, unmount
  cleanup only. Merge-by-key preserved and re-verified.
- **I1** `TextRow` used `bg-white` with `text-steel-dark` — 1.16:1 in dark mode, i.e. the
  user's own typing invisible, and invisible to Task 17's planned
  `bg-steel-dark text-white` grep as well. Switched to the themed `bg-navy-800`
  (17.91:1 light / 14.02:1 dark). Its `<label>` also had no `htmlFor`, so the input had no
  accessible name; fixed with `useId`.
- **I2** `SegmentedRow`'s selected pill went from `bg-steel-highlight/15
  text-steel-highlight` (5 of 10 theme x accent combinations below AA, worst 3.65:1) to
  `bg-navy-800 text-steel-highlight shadow-sm` — an opaque chip on the `steel-ice` track,
  which reduces to accent-on-card. All 10 now pass, worst 5.02:1.
- **I3** The `role="tablist"` promised a pattern it did not deliver. Added
  `settings/ids.ts`, `id` + `aria-controls` on each tab, and a real `role="tabpanel"`
  region on the shell's content wrapper. `SettingsShell` gains a required `activeTab`
  prop so it can label that region.
- **I4** `SegmentedRow`'s `radiogroup` had no roving tabindex and no arrow handler; both
  implemented.
- **I6** A drag started inside the panel and released on the backdrop closed the dialog.
  Guarded with `event.target === event.currentTarget` plus a mousedown-origin check.
- **Minor** `useId` for the dialog title (M3); `role="img"` on `SectionHeader`'s modified
  dot, since ARIA does not permit naming a bare `generic` (M4); `aria-describedby` for
  `ToggleRow`'s hint (M5); zero-visible-items and stale-`devOnly`-selection handling in
  `SettingsNav`, including reclaiming focus the browser drops to `<body>` when the focused
  tab is removed (M7); `[tabindex="-1"]` excluded from the focus trap's selector so its
  first/last match the browser's real tab order (M2).

Deliberately **not** fixed, per the review: I7 (11px secondary text, 2.94–4.38:1) and M1
(off-toggle track, 1.11:1) are verbatim ports from `SettingsModal.tsx` and belong to Task
17's contrast sweep; M6 (capture-phase Escape vs a nested dialog) and M8 (`setLocal`
clobbering an in-flight edit when a debounced echo returns) are Task 11/15 integration
hazards.

One finding **not** in the review list, recorded for Task 17: `SettingsNav`'s active-tab
tint `bg-steel-highlight/10` over `navy-800` measures 4.39:1 for light/amber — the same
defect class as I2, below AA in 1 of 10 combinations. Left alone because the obvious
substitutes do not clear it either (`bg-steel-ice` is 4.43; removing the tint reaches 5.02
but loses the selected affordance), so it needs a design call rather than a token swap.

## Why

The Task 10 report claimed arrow keys "move both DOM focus and `aria-selected` together".
They did not. The original check asserted on appearance, and appearance passes: the
stale-focused button stays inside the `<nav>`, so repeat keydowns keep bubbling and the
selection keeps cycling. A screen reader announces on focus change, so a tablist user
heard nothing. That claim is retracted in place in `.superpowers/sdd/task-10-report.md`,
and every focus assertion in this pass reads `document.activeElement` directly.

## Files touched

- `apps/web-client/src/components/settings/SettingsNav.tsx`
- `apps/web-client/src/components/settings/SettingsShell.tsx`
- `apps/web-client/src/components/settings/useDebouncedPatch.ts`
- `apps/web-client/src/components/settings/ids.ts` (new)
- `apps/web-client/src/components/settings/controls/SegmentedRow.tsx`
- `apps/web-client/src/components/settings/controls/TextRow.tsx`
- `apps/web-client/src/components/settings/controls/ToggleRow.tsx`
- `apps/web-client/src/components/settings/controls/SectionHeader.tsx`
- `.superpowers/sdd/task-10-report.md` (fix-pass section + retraction in place)
- `logs/settings-frontend-foundation_2026-07-27_log.md` (this addendum + the backend
  correction above)

`components/SettingsModal.tsx` untouched. No backend code touched in this pass.

## Track

Cross-cutting (settings overhaul, Phase C fix pass).

## Interfaces / contracts changed

`SettingsShell` now takes a required `activeTab: string` prop — the selected
`NavItem.id` — so it can give its content region `role="tabpanel"` with an
`aria-labelledby` back to the matching tab. Task 11 must pass it. New module
`settings/ids.ts` exports `settingsTabDomId` / `settingsPanelDomId`.

## Verification

`cd apps/web-client && npm run build` → PASS, `tsc -b` strict + `vite build`,
`built in 11.31s`, 0 TS errors, run after the temporary harness was deleted and
`main.tsx` reverted.

Driven live in a browser on Vite `:5173`. `document.activeElement` after each real key
press, starting from `settings-tab-general` in a 5-item nav:

| key | `document.activeElement` after | matches `aria-selected` |
|---|---|---|
| `ArrowDown` | `settings-tab-appearance` | yes |
| `ArrowUp` | `settings-tab-general` | yes |
| `End` | `settings-tab-dev2` | yes |
| `Home` | `settings-tab-general` | yes |
| `ArrowUp` from first (wrap) | `settings-tab-dev2` | yes |

C2 reproduced and confirmed fixed: with focus in a `TextRow` input, 6 forced parent
re-renders left `document.activeElement` on the input every time and the caret unmoved;
8 real keystrokes at 40ms (each re-rendering the parent, with the debounced PATCH landing
300ms later) also held focus. I5: those 8 keystrokes produced 0 patches during typing and
exactly 1 after settling; a radio change plus 5 slider steps in one window coalesced to
`{"mode":"b","temperature":0.5}`. Full detail, including the focus trap, backdrop, M7 and
per-accent contrast tables, is in `.superpowers/sdd/task-10-report.md` under `## Fix pass`.

## Status

Done. Findings applied and verified live; four deferred items recorded above.

## Next

Unchanged: Task 11 assembles `SettingsPanel.tsx` from this shell — note the new required
`activeTab` prop, and that it must call `useDebouncedPatch`'s `flush` on close if its
panel stays mounted behind `open={false}`. Task 17 remains the dark-mode gate and now
carries one extra item (the `SettingsNav` active-tab tint) alongside the 13 existing
`bg-steel-dark text-white` call sites, `ToggleRow`'s off-track, and the 11px secondary
text.
