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
One structural note for that task: there is still no `--color-danger`.

---

## Fix pass — 2026-07-27 (review findings)

### Correction: opacity modifiers DO follow the token
The "Next" section above originally warned that `bg-navy-900/60` and friends "compile to
literal colours and cannot follow a token", and called it the largest item in the sweep.
**That was wrong**, and it would have sent Task 17 chasing call-site rewrites that are not
needed. Tailwind v4 emits *two* rules per `token/NN` utility — a legacy literal, then a
`color-mix()` override inside `@supports (color: color-mix(in lab, red, red))`. Every
browser meeting this app's floor takes the second rule, which resolves `var()` live. The
original claim came from grepping the built CSS, finding the literal, and stopping before
the `@supports` block that immediately overrides it.

The tell was in our own data: the dark scrim measured `oklab(0.951796 … / 0.2)`, which is
the `color-mix()` result — lightness 0.95 is the *dark-mode* ink `#f2ecfa`, not the
light-mode `#1f0e35` a literal would have frozen in. The scrims invert **because** the
opacity utility followed the token, not despite it.

Net effect on Task 17: only `bg-white/N` stays on the sweep list, and it belongs in class
(A) — wrong token chosen, since `--color-white` is Tailwind's built-in and nothing
overrides it — not as an opacity problem. Corrected in full in
`.superpowers/sdd/task-9-report.md` §2.

### `font_scale` could render the page at 0px, unrecoverably
`calc(1rem * var(--font-scale))` renders at **0px** for `NaN`, `0` or a negative value:
`NaN` is a *valid* calc token that clamps to zero for a non-negative length, so there is
no invalid-declaration fallback. At 0px every rem utility collapses — including the
Appearance panel needed to undo it. `1e400` is the mirror image, an 8000px root.

Reachable two ways, neither hypothetical: `PreferencesStore.effective()` re-reads
`preferences.json` and filters by key name only — it never re-validates — so a hand-edited
or stale file flows straight through; and localStorage sits outside server validation
entirely, where the `DEFAULT_APPEARANCE` spread cannot protect a key that is *present* and
bad. Added `clampFontScale()` in `lib/theme.ts`, applied in both `appearanceFromSettings`
and `readCachedAppearance`, and mirrored inline in the pre-paint script (which cannot
import it — it has to run before the bundle).

### Font scale no longer overrides the browser's font-size preference
`calc(16px * …)` → `calc(1rem * …)`. On the root element `rem` resolves against the
browser's *initial* font size, so a user who set their default to 20px keeps it. Identical
behaviour at the default setting.

### Two accents failed WCAG AA as text
The accent block claimed each hue was "checked for >=4.5:1 against its surface". It had
not been. `light.teal #0d9488` measured **3.44:1** on the page background, and the
*default* dark accent `dark.violet #a855f7` measured **4.10:1** on cards. The accent is
used for link and button text, not only fills, so both were real failures.

Changed `light.teal` → `#0f766e` and `dark.violet` → `#c084fc`, and replaced the vague
comment with the measured table. Every hue is now quoted at the worse of its two surfaces
(page `--color-navy-950` and card `--color-navy-800`); all ten clear 4.5:1. Light cards are
white so the page is the tighter constraint there; dark cards are *lighter* than the page,
so the card is tighter in dark.

## Fix-pass verification
- `cd apps/web-client && npm run build` → **PASS**, `✓ built in 14.30s`, 0 TS errors.
- All ten contrast ratios recomputed independently from the committed hex values against
  both surface tokens (WCAG relative-luminance formula): light violet 6.52, indigo 5.77,
  teal 5.02, amber 4.61, rose 5.77; dark violet 6.14, indigo 5.44, teal 8.71, amber 9.71,
  rose 6.02. Worst case 4.61 — all pass. The two replaced values re-measured at 3.44 and
  4.10, confirming they had been failing.

## Blocking note for Task 17
Dark mode is **not shippable** until the sweep lands: 13 `bg-steel-dark text-white` call
sites compute to white-on-white at **1.16:1** in dark mode, including the Send button
(`Composer.tsx:209`) and the settings Done button. Task 17 is a **gate** on shipping the
Appearance panel (Tasks 12/16), not a follow-up to it.
