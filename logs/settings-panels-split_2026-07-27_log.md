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

---

# Task 13 — Model panel gains editable model ids; `web_search_model` regroups to Behavior

- **Date:** 2026-07-27
- **Track:** cross-cutting (web-client UI + backend preferences)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code (Task 13 of the settings overhaul plan)

## What
Turned `ModelPanel`'s read-only cascade readout (persona/technical model, shown
as plain text off `RouterInfo`) into editable `TextRow`s bound to preferences,
and added three more previously-missing model-id fields (artifact, vision,
default agent). All five new inputs use `patchDebounced` and show the server
default as their placeholder when blank.

Also resolved the seam flagged since Task 11's log: `web_search_model` lived in
the backend's `model` group but rendered under `BehaviorPanel`, next to the
`web_search_enabled` toggle that gates it — so editing it from Behavior and
resetting it from Model were two different panels acting on the same field.
Moved the key to the `behavior` group in `EDITABLE_KEYS`
(`services/assistant-core/src/violet_assistant/preferences/store.py`) — a
one-line regroup, no validator change — and updated both panels'
`MODEL_KEYS`/`BEHAVIOR_KEYS` constants to match `keys_in_group()` exactly.
While in `BehaviorPanel`, also fixed its `web_search_model` field's
placeholder, which was a hardcoded literal `"web search model"` instead of the
server default — inconsistent with every other model-id field and the same
blank-shows-default contract this task is about, so gave the panel a
`defaults` prop too.

## Why
Task 3's `ModelResolver` already reads these preference keys at call time, but
nothing in the UI could set persona/technical/artifact/vision/agent-default
model ids — only `llm_model` (indirectly, via provider selection) and
`web_search_model` were reachable. This closes that gap for the remaining five.
The regroup fixes a real UX bug, not a cosmetic one: before this change,
overriding `web_search_model` from Behavior made Behavior's own group-reset a
no-op button (it reset a key it didn't own) while Model's reset silently
cleared a field Model never displayed.

## Files touched
- mod `apps/web-client/src/components/settings/panels/ModelPanel.tsx` —
  `MODEL_KEYS` drops `web_search_model`; cascade `Persona model`/`Technical
  model` become `TextRow`s (was plain `<span>` off `router.persona_model`);
  added `Artifact model`, `Vision model`, `Default agent model` rows; added
  `defaults: SettingsValues` prop.
- mod `apps/web-client/src/components/settings/panels/BehaviorPanel.tsx` —
  `BEHAVIOR_KEYS` gains `web_search_model`; its existing `TextRow`'s
  hardcoded placeholder replaced with `defaults.web_search_model`; added
  `defaults: SettingsValues` prop.
- mod `apps/web-client/src/components/settings/SettingsPanel.tsx` — derives
  `defaults = settings?.defaults ?? {}` once and passes it to both
  `ModelPanel` and `BehaviorPanel`.
- mod `services/assistant-core/src/violet_assistant/preferences/store.py` —
  `web_search_model`'s `PrefSpec` group changed `"model"` → `"behavior"` in
  `EDITABLE_KEYS`. No validator change (`_is_str`, unchanged), no key
  renamed, no new key added — `test_keys_in_group_partitions_all_keys` still
  covers it under its new group without modification.

## Interfaces / contracts changed
- `ModelPanel` and `BehaviorPanel` both now require `defaults: SettingsValues`
  in addition to `PanelProps`, mirroring how `router`/`providers`/etc. are
  passed as panel-specific extras rather than added to the shared
  `PanelProps` type — consistent with Task 11's original pattern for
  `ModelPanel`.
- Backend: `keys_in_group("model")` no longer includes `web_search_model`;
  `keys_in_group("behavior")` now does. `EDITABLE_KEYS` set membership and
  every key's validator are unchanged, so `GET/PATCH/POST /api/settings*`
  response shapes are unchanged — only which group's reset/dot a client-side
  UI attributes the key to.

## Status
done

## Verification
- Backend: `python -m pytest` from repo root, **system interpreter**
  (`C:\Users\arjuna.putranto\anaconda3\python.exe`, the repo `.venv` lacks
  `httpx`/`pytest-asyncio` and was not touched) → **302 passed**, 237
  warnings (pre-existing `on_event`/httpx deprecation noise, unrelated to
  this change), 98.05s. No test pinned `web_search_model` to a specific
  group by name — `test_settings_groups.py`'s
  `test_keys_in_group_partitions_all_keys` only asserts the groups still
  partition the full key set, which they do.
- Frontend: `cd apps/web-client && npm run build` → `tsc -b` clean,
  `✓ built in 15.25s`.
- Browser walkthrough: backend `LLM_PROVIDER=mock` on :8000, vite dev server
  on :5173 (port free, `strictPort: true` never triggered).
  - **Debounce, one PATCH per pause, not per keystroke:** typed `-testxyz`
    (8 chars) into Artifact model with `End` then `type`; exactly **one**
    new `PATCH /api/settings` appeared after the pause, body
    `artifact_model: "qwen/qwen3-coder-testxyz"`. Same result typing 9 chars
    (`-reloadme`) into Vision model. Consistent with
    `useDebouncedPatch`'s single `setTimeout(flush, 300)` that keystrokes
    keep pushing back.
  - **Clear-to-empty persists and falls back:** cleared Artifact model
    entirely (via the browser tool's direct value-set, since this
    environment's synthesized `Backspace` keydown did not trigger native
    text deletion on this input for reasons unrelated to the app — `type`
    and programmatic value-set both worked and both go through the same
    React `onChange`/`patchDebounced` path a real keystroke would). The
    PATCH body carried `artifact_model: ""`; the field then showed the grey
    placeholder `qwen/qwen3-coder` (`defaults.artifact_model`) instead of
    looking broken.
  - **Reload persistence:** full page reload; Vision model still read
    `qwen/qwen3-vl-32b-instruct-reloadme` (typed value survived), Artifact
    model still showed the empty field with the `qwen/qwen3-coder`
    placeholder (empty override also survived, distinctly from "never set").
  - **Group ownership, measured via `GET /api/settings`, not just the UI:**
    overrode `web_search_model` to `...-override` from Behavior. State:
    `overridden: [..., "artifact_model", "vision_model", "web_search_model"]`.
    Clicked **Model**'s Reset section → `overridden` became
    `["ui_mode", "web_search_enabled", "web_search_model"]` and
    `artifact_model`/`vision_model` were back to their defaults —
    `web_search_model` untouched, still `...-override`. Then clicked
    **Behavior**'s Reset section → `overridden: ["ui_mode"]`,
    `web_search_model` back to `deepseek/deepseek-chat-v3.1`. Confirms Model
    no longer claims the key and Behavior's reset actually clears it — the
    exact defect Task 11's log flagged as an open question.
  - **Dev/user mode gating:** with the Model tab visited and dev mode on,
    switched Mode to **User** in General — `Model` and `Agents` tabs and the
    `DEV` nav divider disappeared from the tablist, and the sidebar's
    `Skill Lab` button also disappeared (unrelated dev-gated control,
    confirms the mode flip is real, not a stale snapshot). Switched back to
    **Developer** — both tabs returned.
  - No console errors observed during the walkthrough.
- Cleanup: `data/preferences.json` back to exactly `{"ui_mode":
  "developer"}` (confirmed via `curl /api/settings` showing
  `overridden: ["ui_mode"]` before closing, and reading the file directly).
  Real `.env` untouched. Backend (uvicorn :8000) and vite (:5173) processes
  killed at the end of the session; browser preview stopped.

## Next
- Task 14 (Voice) and Task 15 (Data & privacy) remain; Task 17 still owns
  the dark-mode contrast sweep — this task introduced no new
  `bg-steel-dark text-white` / `bg-white text-steel-dark` pairs (all new
  rows reuse `TextRow`, which already uses the themed `bg-navy-800` token
  per its own comment).

---

# Fix pass — Task 13 review finding (`llm_model` / `web_search_model` bypassed the blank-override guard)

- **Date:** 2026-07-27
- **Track:** cross-cutting (backend preferences / orchestrator)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code (Task 13 review fix)

## What
`ModelResolver.resolve()` (Task 3) treats a blank/whitespace-only preference
override as "unset" and falls back to `Settings`. Five model-id keys go
through it. Two — `llm_model` and `web_search_model` — were instead read
inline in `chat_orchestrator.py` via `prefs.get(key, self.settings.key)`,
whose default arm is dead code (`PreferencesStore._defaults()` always seeds
both keys, so `.get` never falls through). An emptied field therefore sent
`model=""` to the provider; for `web_search_model` specifically,
`web/search.py` builds `online_model = "" + ":online"` and POSTs `":online"`
as the model id.

Task 13 gave `web_search_model`'s input the same "clear the field to use the
default" placeholder contract the five resolver-backed fields already
promise, making the one field where clearing silently breaks the request
reachable from the UI.

Fixed by giving `ChatOrchestrator` an optional `resolver: ModelResolver`
(threaded from `main.py`'s existing `model_resolver`, which was already built
but never passed in) and replacing both inline lookups with a private
`_resolve_model(key, prefs)` helper that calls `resolver.resolve(key)` when a
resolver is present, falling back to the old `prefs.get(...)` only for
callers/tests that construct `ChatOrchestrator` without one.

## Why
Reused `ModelResolver` rather than hand-rolling a second `.strip() or
default` guard at each call site, per the review note — a second
implementation of the same guard is exactly the kind of duplication that lets
one copy drift from the other (which is how this bug happened: five keys got
the guard, two didn't). Threading a resolver into `ChatOrchestrator` was not
awkward — `main.py` already constructs `model_resolver = ModelResolver(preferences,
active_settings)` and passes it to four other components; it simply was not
also passed to `ChatOrchestrator`.

## Files touched
- mod `services/assistant-core/src/violet_assistant/orchestrator/chat_orchestrator.py`
  — added `resolver: ModelResolver | None = None` constructor param (stored as
  `self.model_resolver`), added `_resolve_model(key, prefs)` helper, and
  routed the `llm_model` (base_options) and `web_search_model` (web-search
  branch) lookups through it. `resolve()` itself and the five keys already
  using it are unchanged.
- mod `services/assistant-core/src/violet_assistant/main.py` — passes
  `resolver=model_resolver` into the existing `ChatOrchestrator(...)` call
  (one line; `model_resolver` already existed for the other four sites).
- mod `services/assistant-core/tests/test_chat_orchestrator.py` — new
  `test_llm_model_blank_override_falls_back_to_settings` and
  `test_web_search_model_blank_override_falls_back_to_settings`
  (parametrized over `""` and `"   "`), mirroring
  `test_blank_override_falls_back` in `test_model_resolver.py` but asserting
  on the model id that actually reaches the provider/request payload
  (`_RecordingProvider.models`, `_RecordingWebProvider.models`) rather than a
  helper's return value. The web-search test asserts the exact resolved
  payload model, not just a `.endswith(":online")` suffix check (which a
  blank override also satisfies) — proving `":online"` alone can no longer be
  produced.

## Interfaces / contracts changed
- `ChatOrchestrator.__init__` gains one optional keyword arg (`resolver`,
  default `None`); every existing call site (`main.py`, all pre-existing
  tests) keeps working unchanged since none passed a resolver before. No
  route/schema/env-var change. `ModelResolver.resolve()`'s semantics and the
  five keys already using it are untouched.

## Status
done

## Verification
Ran from repo root with the **system interpreter** (repo `.venv` lacks
`httpx`/`pytest-asyncio`, not touched):

```
python -m pytest -q
```
→ **306 passed**, 237 warnings (pre-existing `on_event`/httpx deprecation
noise, unrelated), ~90s. 306 = the prior 302 baseline + the 4 new
parametrized cases.

Targeted run before the full suite:
```
python -m pytest services/assistant-core/tests/test_chat_orchestrator.py services/assistant-core/tests/test_model_resolver.py -q
```
→ 24 passed.

### Mutation check (the standard on this branch)
Reverted only the two call sites back to the pre-fix `prefs.get("llm_model",
self.settings.llm_model)` / `prefs.get("web_search_model",
self.settings.web_search_model)` (guard removed, `_resolve_model` helper and
constructor param left in place), then reran the new tests:

```
python -m pytest services/assistant-core/tests/test_chat_orchestrator.py -k "blank_override" -q
```
→ **4 failed** (all four parametrized cases), e.g.
`AssertionError: assert ['   :online'] == ['deepseek/deepseek-chat-v3.1:online']`
— confirms the tests fail without the guard, not just pass with it.

Restored both call sites to `self._resolve_model(...)` and reran the full
suite:
```
python -m pytest -q
```
→ **306 passed** again, confirming the fix and tests are back to green.

`data/preferences.json` was never touched by this pass (no server was run);
confirmed via `git status --porcelain` showing no change to it. Real `.env`
untouched.

## Next
- None outstanding from this fix. The remaining open item from Task 13's log
  (Task 17's dark-mode contrast sweep) is unrelated to this backend-only
  change.
