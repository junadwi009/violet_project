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
