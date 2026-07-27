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
