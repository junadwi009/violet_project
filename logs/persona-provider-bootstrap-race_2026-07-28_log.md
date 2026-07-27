# Persona/provider bootstrap race + reset resync (Task 16 fix pass)

- **Date:** 2026-07-28
- **Track:** 1 Chat (web client bootstrap) — cross-cutting with settings
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code

## What

Removed the bootstrap ordering race in `apps/web-client/src/App.tsx` that let a
stored `default_personality` / `default_provider` naming something the server no
longer offers survive into app state. Seeding from `/api/settings` and
validating against `/api/personalities` + `/api/providers` are now one ordered
step inside a single `Promise.all`, instead of two sibling promise chains whose
interleaving decided the outcome. Added a one-shot persona/provider resync on a
settings **group reset**.

## Why

Task 16 (`49f1a4d`) made persona/provider persist by seeding both from stored
preferences in the `fetchSettings()` chain, while the fallback guard that
corrects an unresolvable id lived in the separate `Promise.all` chain. Switching
the guard to functional updaters only guaranteed it reads current state *when it
runs* — not that it runs *after* the seed. Both orderings were reachable:

- `/api/settings` slow → seed, then guard → corrected.
- `/api/personalities` slow → guard, then seed → **dead id survived**.

In the losing state the persona picker rendered with nothing selected (it
compares against the fetched list) and every `POST /api/chat` returned 500:
`FileNotFoundError: Personality profile not found: violet.devoted_strategist`
(`personality/loader.py:28` via `chat_orchestrator.py:110`). This was a
regression introduced by the seeding: before it, `personalityId` could only hold
`violet.default` or an id rendered from the fetched list. The backend's `_is_str`
validator accepts any string for both keys, so an unresolvable value is storable.

Provider side had the same structural bug, milder: chat still returns 200
(backend degrades on an unknown provider) but the composer chip rendered the raw
id (`bogus_provider`) instead of a label.

Separately, a "General" group reset cleared both keys server-side without
resyncing the open picker: the section's "modified" dot cleared while the picker
still showed the pre-reset value, and the session kept *sending* the pre-reset
persona/provider until reload.

## Files touched

- `apps/web-client/src/App.tsx` — new `resolveOffered()` helper (the shared
  invariant: the id in state is always one the server offers); bootstrap effect
  restructured so one shared `fetchSettings()` promise feeds both an independent
  `setAppSettings` and the ordered seed-then-validate step; one-shot reset
  resync handler; corrected the misleading comment claiming functional updaters
  made the guard race-safe.
- `apps/web-client/src/components/settings/SettingsPanel.tsx` — `onSettingsRefreshed`
  renamed to `onSettingsReset` (it is only ever called from `handleReset`, and
  App now also uses it to resync state it holds outside `values` — correct only
  as a one-shot on that event).

## Interfaces / contracts changed

`SettingsPanelProps.onSettingsRefreshed` → `onSettingsReset` (internal prop,
single call site). No API, schema, or env-var change.

## Deliberately NOT done

No recurring resync effect keyed on `[appSettings]`. The bootstrap correction of
an invalid stored id is deliberately not written back to the server, so such an
effect would re-apply the stale invalid id after any unrelated PATCH. The reset
resync is a one-shot on that one event, and is a no-op for other groups because
`resolveOffered` returns `current` when the incoming value is unchanged.

## Status

done

## Verification

`cd apps/web-client && npm run build` → `tsc -b && vite build`, **PASS**,
`✓ built in 18.07s` (pre-existing >500 kB chunk advisory only).

Real app, both interleavings forced with a delay proxy (stdlib Python, in front
of the backend on :8010; client pointed at it via `VITE_API_BASE_URL`). Backend
isolated: `DATABASE_URL=sqlite:///./.tmp/task16fix/scratch.db`,
`MEMORY_DIR=./.tmp/task16fix/memory`, `LLM_PROVIDER=mock`. Unresolvable stored
values: `default_personality: violet.devoted_strategist` with
`configs/personality/violet.devoted_strategist.json` renamed away (`/health`
listed only `violet.default`), and `default_provider: bogus_provider`.

| Run | `personalityId` | Picker | `POST /api/chat` |
|---|---|---|---|
| **Control, pre-fix code**, `/api/settings` delayed 1.5s | `violet.devoted_strategist` (dead) | "Violet" rendered **not selected**; chip read `bogus_provider` | **failed** — backend traceback `FileNotFoundError: Personality profile not found: violet.devoted_strategist` |
| **Fixed**, `/api/settings` delayed 1.5s | `violet.default` | "Violet" selected; chip "Mock" | **200**, "Response received" |
| **Fixed**, `/api/personalities` delayed 1.5s | `violet.default` | "Violet" selected; chip "Mock" | **200** |
| **Fixed**, no delay ×3 | `violet.default` each time | selected each time; chip "Mock" | — |

Reset resync: with both profiles restored, stored persona "Devoted Strategist"
seeded and shown selected → "Reset section" on General → picker snapped to
"Violet" with no reload, and the next `/api/chat` body carried
`"personality_id":"violet.default","provider":"mock"` (captured via a `fetch`
wrapper in the page).

Persistence (Task 16's original behaviour) re-checked, unbroken: clicking
"Devoted Strategist" wrote `default_personality` to `data/preferences.json` and
survived a reload.

Cleanup: `configs/personality/violet.devoted_strategist.json` restored, backend
restarted, `/health` confirmed `['violet.default', 'violet.devoted_strategist']`;
`data/preferences.json` restored by copying back the backup taken before the run
(exactly `{"ui_mode": "developer"}`); scratch DB/memory dir removed; proxy,
backend and Vite stopped. `data/violet.db` never read or written; "clear all
sessions" never run; real `.env` untouched.

## Next

None for this defect. Standing unrelated item: two `Received NaN for the value
attribute` React warnings on first paint.
