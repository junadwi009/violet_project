# Dark theme tokens, accent, density, font scale

- **Date:** 2026-07-27
- **Track:** cross-cutting (settings overhaul, Task 9 of 18)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code

## What
Added the CSS-token machinery that the upcoming Appearance settings panel will drive:
a `[data-theme="dark"]` override of the nine palette tokens, `--color-success` /
`--color-warning` semantic tokens, four accent overrides (x2 for dark), a
`--font-scale` root multiplier, and a `--row-pad` density variable. Added
`src/lib/theme.ts` to stamp these onto `<html>`, and a synchronous pre-paint script in
`index.html` so a dark-theme user does not flash light while `/api/settings` is in flight.

## Why
Dark mode, accent choice, UI density and font size are part of the settings overhaul.
Driving them through the existing `@theme` tokens means every utility that already goes
through a token inverts with no per-component work. `--color-steel-dark` intentionally
flips from near-black to near-white: it is the primary ink token, and its name describes
its light-mode value, not its role.

## Files touched
- `apps/web-client/src/index.css` — dark/accent/density/font-scale rules appended after `@theme`
- `apps/web-client/src/lib/theme.ts` — new
- `apps/web-client/index.html` — pre-paint script in `<head>`
- `.superpowers/sdd/task-9-report.md` — full report incl. the hardcoded-colour sweep list

No backend code touched. No new dependencies. No test framework added (the frontend has
none and this plan does not add one).

## Interfaces / contracts changed
New module `apps/web-client/src/lib/theme.ts` exports:
`Appearance`, `ThemeChoice`, `DensityChoice`, `AccentChoice`, `DEFAULT_APPEARANCE`,
`applyAppearance()`, `appearanceFromSettings()`, `readCachedAppearance()`,
`writeCachedAppearance()`, `watchSystemTheme()`.
New DOM contract: `<html data-theme data-density data-accent style="--font-scale">`.
New `localStorage` key: `violet.appearance` (paint hint only; server value overwrites).
Consumes `SettingsValues` from `lib/api.ts` (Task 8). No env vars added.

## Status
done — nothing imports the module yet; Task 12 adds the Appearance panel and Task 16
wires it into the app.

## Verification
- `cd apps/web-client && npm run build` (`tsc -b` strict + `vite build`) → **PASS**,
  `✓ built in 9.20s`, 0 TS errors.
- Runtime check against backend on :8000 and Vite on :5173.
  Pre-paint script stamped `theme/density/accent/--font-scale` before React ran.
  `document.documentElement.dataset.theme = "dark"` inverts background, sidebar, cards,
  borders and body ink (verified by screenshot and computed-style diff).
  All 10 theme x accent combinations resolve to the exact intended hex values.
  `--font-scale` 0.875 / 1 / 1.25 → html 14 / 16 / 20px, and every rem utility scales
  proportionally (`text-3xl` 26.25 / 30 / 37.5px).
  `data-density="compact"` flips `--row-pad` 0.75rem → 0.5rem.

## Next
Task 17 sweeps the hardcoded colours. The full list is in
`.superpowers/sdd/task-9-report.md` §4 — three classes:
(A) `bg-white` / `bg-white/N` / `glass-panel` / raw emerald-amber-red palette entries that
stay light; (B) `bg-steel-dark text-white` pairs that invert into white-on-white;
(C) `bg-steel-dark/20|30` modal scrims that become a light haze in dark mode.
Two structural notes for that task: opacity-modifier utilities (`bg-navy-900/60`) compile
to literal colours and cannot follow a token, and there is still no `--color-danger`.
