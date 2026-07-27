# Settings modal split into per-group panels

- **Date:** 2026-07-27
- **Track:** cross-cutting (web-client UI)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code (Task 11 of the settings overhaul plan)

## What
Replaced the 501-line single-column `components/SettingsModal.tsx` with six
per-group panels assembled behind the Phase C shell
(`components/settings/SettingsPanel.tsx`), and swapped `App.tsx` over. The old
file is deleted.

## Why
Ten unrelated concerns shared one scrolling column, which blocked every
follow-up task (appearance controls, voice, data & privacy, reset-per-group).
Doing the move as a behavior-neutral step of its own keeps any later regression
bisectable to one of two commits.

## Files touched
- new `apps/web-client/src/components/settings/SettingsPanel.tsx` (shell + nav + panel switch + debounced patch + group reset)
- new `apps/web-client/src/components/settings/panels/{General,Model,Behavior,Skills,Agents,Knowledge}Panel.tsx`
- mod `apps/web-client/src/App.tsx` (import + element rename only; every prop unchanged) — shared seam
- del `apps/web-client/src/components/SettingsModal.tsx`

## Interfaces / contracts changed
- `SettingsPanel` takes the same props `SettingsModal` did, plus optional
  `onDeleteAllSessions` (declared for Task 15; not yet consumed).
- Panels consume the Task 10 `PanelProps` (`values` / `overridden` / `patch` /
  `devMode`) plus per-panel extras.
- Group reset goes through `POST /api/settings/reset` then a no-op
  `PATCH /api/settings` with `{}` to push the fresh payload back to App, which
  owns `appSettings`. No backend change.
- Two intentional behavior changes: temperature moved from the Behavior group to
  the Model panel; the decorative Palette section deleted ahead of Task 12.

## Status
done

## Verification
- `cd apps/web-client && npm run build` → `tsc -b` clean, `✓ built in 12.07s`.
- Browser walkthrough against `LLM_PROVIDER=mock RAG_PROVIDER=vector
  EMBED_PROVIDER=mock` backend on :8000 + vite on :5173. Every nav entry
  exercised: mode toggle hides/shows the dev tabs, persona and agent selection
  reach App (next chat turn rendered `↳ ANALYST`), all three behavior toggles
  flip and persist, knowledge counts match `GET /api/knowledge`, Reindex logged
  `POST /api/knowledge/reindex → 200` and reported `Indexed 0, skipped 1,
  removed 0`, all 12 skills match `GET /api/skills`, Skill Lab opens, per-group
  Reset restores defaults, Escape/X/backdrop close and return focus to the
  Settings trigger. Preference state restored afterwards.
- Flush-on-close proven: slider change + Escape in one tick, server had the new
  value 120 ms later, inside the 300 ms debounce window.
- Full detail in `.superpowers/sdd/task-11-report.md`.

## Next
- Task 12 replaces the Appearance placeholder; Task 14 Voice; Task 15 Data &
  privacy (needs `onDeleteAllSessions` wired in `App.tsx`).
- Task 17 owns the dark-mode contrast inventory; two moved call sites
  (`bg-white` on Knowledge's "Full rebuild", and the moved `bg-steel-dark`
  pairings) were left untouched on purpose and are commented in place.
- Open question for Task 12/13: `web_search_model` sits in the backend `model`
  group but renders under Behavior, so Behavior's group reset cannot clear it.

---

# Fix pass — review findings on the panel split

- **Date:** 2026-07-27
- **Track:** cross-cutting (web-client UI)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code (Task 11 review fixes)

## What
Four behavior regressions the split introduced, plus two minors:

1. **Un-debounced the click-driven controls.** `PanelProps` now carries two write
   channels instead of one: `patchDebounced` (300 ms, `SliderRow` / `TextRow`
   only — they render from local state) and `patchNow` (immediate, `ToggleRow` /
   `SegmentedRow` — they render from `values`, so a debounce lags the visible
   state by the whole window and makes two rapid taps coalesce into one net
   flip).
2. **`web_search_model` is counted by `ModelPanel`, not `BehaviorPanel`.** Both
   key lists now equal `keys_in_group()` for their group. The control has not
   moved — placement is Task 12/13's call — only the counting changed.
3. **Deleted the empty `PATCH {}` after a reset.** It was not a server-side
   no-op: `PreferencesStore.patch` rewrites `preferences.json` unconditionally.
   `SettingsPanel` gained an `onSettingsRefreshed(next)` prop (App passes
   `setAppSettings`) and `handleReset` uses the payload `resetSettings` already
   returns.
4. **`handleReset` discards the queue instead of flushing it.** `flush()` *sent*
   the pending PATCH, racing the reset with no ordering guarantee. Added
   `cancel()` to `useDebouncedPatch` and called that.
5. (M4) `KnowledgePanel` returns `null` when `knowledge === null`, and
   `ModelPanel` returns `null` when `devMode` is false — no orphan `SectionHeader`
   with a live "Reset section" over an empty panel.
6. (M5) `activeTab` resets to General when `open` goes false, so reopening does
   not land on the last tab. Keyed on `open`, not `handleClose`, so the paths
   that bypass it (App closes Settings when the Skill Lab opens) are covered.

## Why
The task's central requirement was behavior neutrality; these four changed
behavior. #1 is measurable latency the user feels on every toggle, and it also
drops input (double-tap). #2 made one reset button lie and hid the one that
works. #3 and #4 are latent data hazards whose comments claimed they were safe.

## Files touched
- mod `apps/web-client/src/components/settings/SettingsShell.tsx` — `PanelProps`
  split into `patchDebounced` / `patchNow`, each documented
- mod `apps/web-client/src/components/settings/SettingsPanel.tsx` — both channels
  wired, `onSettingsRefreshed` prop, `handleReset` rewritten, tab reset effect
- mod `apps/web-client/src/components/settings/useDebouncedPatch.ts` — added
  `cancel()`
- mod `apps/web-client/src/components/settings/panels/{General,Behavior,Model,Knowledge}Panel.tsx`
- mod `apps/web-client/src/App.tsx` — `onSettingsRefreshed={setAppSettings}` — shared seam

## Interfaces / contracts changed
- `PanelProps.patch` → `PanelProps.patchDebounced` + `PanelProps.patchNow`.
  Every panel that writes preferences must now pick one; the wrong pick is a
  visible bug, so both are commented at the definition and at each call site.
- `SettingsPanelProps` gains required `onSettingsRefreshed: (next: AppSettings) => void`.
- `useDebouncedPatch` returns `{ push, flush, cancel }`.
- No backend change.

## Status
done

## Verification
`cd apps/web-client && npm run build` → `tsc -b` clean, `✓ built in 14.72s`.

Measured in the real app (backend `LLM_PROVIDER=mock` on :8000, vite on :5173),
instrumenting `window.fetch` for timings and a `MutationObserver` on
`aria-checked` for the UI flip:

| Measurement | Before (report) | After |
|---|---|---|
| Canvas toggle: PATCH dispatched | +300 ms | **+1 ms** |
| Canvas toggle: `aria-checked` flips | ~750 ms | **119 ms** (round-trip 56 ms) |
| Mode segmented control: `aria-checked` flips | 750 ms | **145 ms** (round-trip 105 ms) |
| Two taps 80 ms apart | 1 net flip, 1 request | **2 net flips, 2 requests** (`false` then `true`), server back to start |
| Temperature drag, 6 steps in 180 ms | 1 request (unchanged) | **1 request** (`{"temperature":0.8}`), thumb tracked live |

- With `web_search_model` the only override (`overridden: ["ui_mode",
  "web_search_model"]`): **Behavior** → no dot, Reset section **disabled**;
  **Model** → dot, Reset section **enabled**. Clicking Model's reset cleared it
  (`overridden: ["ui_mode"]`, value back to `deepseek/deepseek-chat-v3.1`).
- That reset fired **exactly one** request — `POST /api/settings/reset` — and no
  `PATCH`; the dot and button updated from its response.
- Queued-edit-vs-reset: dragged temperature to 1.7, clicked Reset 50 ms later.
  Only the reset went out, no `temperature` PATCH at all, slider snapped to 0.2.
  The old `flush()` would have raced 1.7 against it.
- With the backend stopped (`knowledge === null`), the Knowledge tabpanel renders
  0 characters — no header, no Reset button. Behavior still renders its defaults
  (M1, unchanged).
- Tab reset: opened on General → navigated to Knowledge → Escape → reopened on
  **General**.
- Flush-on-close still holds: slider to 0.9 + Escape in one tick, server had 0.9
  120 ms later.
- No console errors. `data/preferences.json` restored to `{"ui_mode":
  "developer"}` and `overridden` back to `["ui_mode"]`.

## Next
- Task 12/13 still owns *where* `web_search_model` renders (Behavior) versus what
  group resets it (Model). Only the miscount is fixed.
- `ModelPanel`'s `!devMode → null` is defensive: the nav already hides that tab
  in user mode and the tab now resets on close, so the state is not reachable
  through the UI.

---

# Task 12 — Appearance panel

- **Date:** 2026-07-27
- **Track:** cross-cutting (web-client UI)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code (Task 12 of the settings overhaul plan)

## What
Added the Appearance panel (theme, density, font size, accent) and wired it
into `SettingsPanel`'s nav switch and into `App.tsx`, which now applies
`appearanceFromSettings(appSettings.values)` on every settings change,
writes it to the `violet.appearance` localStorage cache, and follows OS theme
changes live while `theme === "system"`. This is the first task that makes
Task 9's theme machinery reachable from the UI.

## Why
Task 11 shipped the shell with the Appearance tab still a placeholder. Theming
was fully built (tokens, `applyAppearance`, the pre-paint `index.html` script)
but nothing in the app ever called it from user input.

## Files touched
- new `apps/web-client/src/components/settings/panels/AppearancePanel.tsx`
- mod `apps/web-client/src/components/settings/SettingsPanel.tsx` — import +
  `case "appearance"` in `renderPanel()` (was falling through to the "Coming in
  the next task" default)
- mod `apps/web-client/src/App.tsx` — theme import + an effect that applies and
  caches appearance and subscribes to `watchSystemTheme` — shared seam

## Interfaces / contracts changed
- None. Consumes `PanelProps` (Task 10), `Appearance` / `AccentChoice` /
  `applyAppearance` / `appearanceFromSettings` / `writeCachedAppearance` /
  `watchSystemTheme` (Task 9) exactly as exported, and the `theme` /
  `ui_density` / `font_scale` / `accent` backend keys (Task 2) unchanged.

## Write-channel choice
- `patchNow` (immediate) for **Theme**, **Density**, and the **Accent**
  swatches — all three are click-driven and render straight from `values`
  with no local state, so a debounce would only add latency, not hide it (see
  the rationale comment on `patchNow`/`patchDebounced` in `SettingsShell.tsx`
  and `SettingsPanel.tsx`).
- `patchDebounced` (300 ms) for **Font size** only — `SliderRow` holds local
  state and fires on every drag step, so debouncing coalesces a drag into one
  PATCH / one file write instead of one per step.

## Defensive coercion added beyond the brief's sample code
`theme` and `ui_density` come from server state, not a click handler, so an
out-of-range value (hand-edited `preferences.json`, a stale file) is possible
even though the backend validates on write. `SegmentedRow` reports the
*first* option as `aria-checked` for any `value` outside `options` — for
Theme that's "Light", which is not the applied default ("system"). Coerced
both (and `accent`, defensively) to a known option before handing them to
`SegmentedRow`/the swatch buttons, falling back to `DEFAULT_APPEARANCE` so the
displayed selection can never silently disagree with what's actually painted
on screen. `font_scale` is left to `SliderRow`'s existing `Number(...)`
coercion plus `appearanceFromSettings`'s own `clampFontScale` — not
duplicated here.

The five accent swatches use hardcoded hex values on purpose (each must show
its true hue in both themes) and are commented in place so Task 17's
`bg-steel-dark`/`bg-white` contrast sweep does not "fix" them.

## Status
done

## Verification
- `cd apps/web-client && npm run build` → `tsc -b` clean, `✓ built in 18.38s`.
- Browser walkthrough: backend `LLM_PROVIDER=mock` on :8000 (`GET /health` →
  `provider.status: "ok"`), vite dev server on :5173 via the project's
  `.claude/launch.json` (`violet-web-client`, port 5173, `strictPort: true`
  never triggered — port was free).
  - Theme → Dark: UI inverted immediately, no reload; `<html data-theme>`
    flipped synchronously with the click.
  - Reload while dark: page reloaded and rendered dark; `localStorage
    violet.appearance` held `{"theme":"dark",...}` before the reload, so the
    `index.html` pre-paint script (Task 9, unmodified) had the value available
    before the bundle ran. No white flash observed in the post-load
    screenshot.
  - Theme → System, then emulated the OS scheme to dark via the browser tool's
    `colorScheme` control (no page reload in between):
    `document.documentElement.dataset.theme` flipped from `"light"` to
    `"dark"` and `window.matchMedia('(prefers-color-scheme: dark)').matches`
    went `true`, confirming `watchSystemTheme`'s change listener is live.
  - Font size: cleared `performance` resource timings, focused the slider and
    pressed ArrowRight 6 times (steps through the debounce exactly like a mouse
    drag), waited past 300 ms. **Exactly one** `fetch` entry to
    `/api/settings` appeared (duration 47.0 ms) — one PATCH for a 6-step drag,
    not six.
  - Theme/Density/Accent round-trip timing, measured via
    `performance.getEntriesByType('resource')` immediately after each click:
    Dark theme click and Density click were visually instantaneous (UI flips
    before the request even resolves, since both render from `values` which
    only the response updates); the Accent → Teal click's PATCH measured
    **39.0 ms**. All comfortably inside the "immediate, one round-trip"
    expectation and nowhere near the old 300 ms debounce.
  - Accent → Teal: propagated live to the active-tab highlight in Settings'
    own nav and the slider thumb, confirming the CSS token wiring from Task 9
    is being driven correctly, not just the swatch itself.
  - Reset section: after Theme=Dark→System(still dark, OS emulated dark),
    Density=Compact, Font=17px, Accent=Teal, clicked "Reset section" — Theme
    back to System, Density back to Cozy, Font size back to 16px, Accent back
    to Violet, modified dot cleared, button disabled again. `data/
    preferences.json` came back to exactly `{"ui_mode": "developer"}` (its
    pre-test content) with no leftover appearance keys — no manual restore
    needed.
- Newly visible in dark mode (not introduced by this task — Task 17's known
  13 `bg-steel-dark text-white` / `bg-white text-steel-dark` call sites,
  called out as expected in the brief): with Theme=Dark the composer's Send
  button renders as a near-invisible light-on-light circle, the two
  quick-prompt suggestion pills and the workspace header bar stay light-grey
  against the dark canvas, and the floating-tools rail keeps a light pill
  background. All consistent with the documented ~1.16:1 contrast defect;
  none of it is in a file this task touched.

## Next
- Task 17 sweeps the `bg-steel-dark text-white` / `bg-white text-steel-dark`
  inventory (Send button, quick-prompt pills, header bar, floating-tools rail
  observed above) — this task's dark-mode walkthrough is additional evidence
  for that sweep, not a fix.

---

# Fix pass — Task 12 review findings (malformed server values)

- **Date:** 2026-07-27
- **Track:** cross-cutting (web-client UI)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code (Task 12 review fixes)

## What
A reviewer re-measured Task 12 under instrumentation with a hand-edited
`data/preferences.json`. Functional core (write channels, no pre-paint
flash, system-theme following, listener balance, reset, font-scale page
clamp) was confirmed solid and untouched. Four findings, all in
malformed-server-value handling:

1. **(IMPORTANT) Theme coercion masked a real disagreement.**
   `appearanceFromSettings` in `lib/theme.ts` used `??`, which only catches
   `null`/`undefined` — a bad `theme` value (e.g. `"purple"`) reached
   `applyAppearance` verbatim and was stamped on `<html>` with no matching
   CSS rule, while `AppearancePanel`'s separate coercion displayed "System".
   Worse: `App.tsx` only subscribes to `watchSystemTheme` when
   `appearance.theme === "system"`, and the *applied* (uncoerced) value was
   `"purple"`, not `"system"` — so the subscription never registered. The
   panel advertised OS-following that would never happen.
2. **(IMPORTANT) Panel rendered "NaNpx".** `AppearancePanel` computed
   `Number(values.font_scale ?? DEFAULT_APPEARANCE.fontScale)` directly; `??`
   doesn't catch a present-but-bad value, so `font_scale: "not-a-number"`
   produced `NaN`, visible in the slider label and a stale thumb position.
   The page's own clamp was fine — the panel's was not.
3. **(MINOR) Accent swatch group had no accessible name or grouping** —
   five `aria-pressed` toggle buttons with no `role="group"` or
   `aria-labelledby`, inconsistent with the panel's own `role="radiogroup"`
   pattern used for Theme/Density.
4. **(MINOR) Swatch comment overstated the hexes** — claimed each swatch
   shows its "TRUE hue in both themes"; the hexes are fixed light-palette
   values that don't match the theme-dependent applied token (e.g. teal
   applies `#0f766e` light / `#2dd4bf` dark). Hue-*family* indicator, not
   true-hue.

Two rationales from the original Task 12 report were contradicted by
measurement and corrected in place in `.superpowers/sdd/task-12-report.md`:
the claim that `appearanceFromSettings` already fell back to `"system"` for
a bad theme (it used `??`, so it did not), and the claim that `font_scale`
was "already covered" by the page-level clamp (that clamp protects the
painted page, not the panel's own `Number(...)` read).

## Why
Both IMPORTANT findings shipped because their stated rationale sounded
right and nobody had hand-edited `preferences.json` to check. The backend
validates preference writes, but `PreferencesStore.effective()` re-reads
`data/preferences.json` and filters by key *name* only — never re-validates
— so a hand-edited or stale file serves bad values to the client verbatim.
That's the path both findings travel.

## Files touched
- mod `apps/web-client/src/lib/theme.ts` — added `coerceTheme` /
  `coerceDensity` / `coerceAccent` (validated against explicit
  `THEME_VALUES` / `DENSITY_VALUES` / `ACCENT_VALUES` sets) and wired them
  into `appearanceFromSettings`, which is now the single source of truth
  both `App.tsx` and `AppearancePanel` derive from.
- mod `apps/web-client/src/components/settings/panels/AppearancePanel.tsx`
  — removed the panel-local `theme`/`density`/`accent` coercion blocks in
  favor of `appearanceFromSettings(values)`; `SliderRow`'s `value` now reads
  the same call's `fontScale` instead of a raw `Number(...)`; added
  `role="group"` + `aria-labelledby` (via `useId()`) to the accent swatch
  container; reworded the `ACCENTS` hardcoded-hex comment.

## Interfaces / contracts changed
- None externally. `appearanceFromSettings` (Task 9) keeps its signature —
  only its internal coercion got stricter. No backend change.

## Status
done

## Verification
`cd apps/web-client && npm run build` → `tsc -b` clean, `✓ built in 17.09s`.

Measured in the real app (backend `LLM_PROVIDER=mock` on :8000, vite dev
server on :5173, then re-checked against the production build via
`vite preview --port 4173 --strictPort` since pre-paint checks are only
valid there — the dev server injects CSS via JS):

| Case | Before | After |
|---|---|---|
| `theme: "purple"`, OS emulated dark — panel | "System" | "System" (unchanged, now honest) |
| `theme: "purple"`, OS emulated dark — `data-theme` | `"purple"` | `"dark"` |
| `theme: "purple"`, OS emulated dark — `bodyBg` | `rgb(247,244,250)` (light) | `rgb(20,16,28)` (dark) |
| `theme: "purple"` — OS-follow subscription | never registers | live: flipping emulated scheme dark→light flips `data-theme` and `bodyBg` in the same tab, no reload |
| `font_scale: "not-a-number"` — panel label | `"NaNpx"` | `"16px"` |
| `font_scale: "not-a-number"` — slider thumb | stale `1.075` | `"1"` (matches label and `--font-scale`) |
| `font_scale: "not-a-number"` — page `--font-scale` | `1` (already correct) | `1` (unchanged) |

Regression check (via `window.fetch` instrumentation, not just visual
inspection):
- Theme click → Dark: single `PATCH /api/settings` `{"theme":"dark"}`,
  fired synchronously with the click (`patchNow`, unchanged).
- Accent click → Teal: single `PATCH /api/settings` `{"accent":"teal"}`
  (`patchNow`, unchanged).
- Font-size: dispatched a 5-step drag (1.025 → 1.125) programmatically;
  exactly **one** `PATCH /api/settings` fired, body `{"font_scale":1.125}`
  (`patchDebounced` coalescing, unchanged).

Accent group a11y: `role="group"` on the swatch container, `aria-labelledby`
resolves to an element with text `"Accent"` — confirmed via DOM query.

Both dev (:5173) and preview (:4173) servers, plus the backend (:8000),
stopped at the end of this pass. `data/preferences.json` restored to
`{"ui_mode": "developer"}`, confirmed via `git diff` showing no changes to
that file.

## Next
- None outstanding from this pass. Task 17 still owns the dark-mode
  contrast sweep noted in the original Task 12 entry above; unaffected by
  this fix pass.
