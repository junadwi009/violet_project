# Dark-mode contrast sweep (Task 17)

- **Date:** 2026-07-28
- **Track:** cross-cutting (web-client theme)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code

## What

Swept the whole web client for colour pairings that fail WCAG AA, in **both** themes and
across the accent picker, and fixed what the sweep found. The headline defect — the Send
button and the settings Done button computing **1.16:1 white-on-white in dark mode** — is
gone, along with 40 further defect groups the original brief's grep could not see.

Root causes fixed, in order of blast radius:

1. **`text-white` on token-driven fills** (12 sites). `--color-steel-dark` inverts to
   near-white in dark, so `bg-steel-dark text-white` was 1.16:1. Replaced with
   `text-navy-950`, the ink token that inverts *with* the fill (15–17:1 both themes).
   Same fix for `bg-steel-highlight text-white` (1.67:1 at dark/amber) and the solid
   semantic fills in MemoryDrawer.
2. **`bg-white` as a surface** (16 sites, plus `.glass-panel` in CSS). A literal `#fff`
   that no theme override can reach — every one of these stayed a white slab on the dark
   canvas with near-white text on it (1.06–2.26:1). Routed to `bg-navy-800`, which is
   `#ffffff` in light, so light mode is byte-identical.
3. **The `text-steel/50|60|70` tertiary ramp** (47 sites). An opacity modifier on
   `--color-steel` has no contrast budget: /50 was 2.25 light / 1.33 dark, /70 was
   3.35 / 4.38. Replaced the whole ramp with one new token, `--color-steel-muted`.
4. **Raw Tailwind palette entries** (21 sites: `emerald-*`, `amber-*`, `red-*`, and a
   hardcoded `#c77dff` gradient stop). Routed to the semantic tokens. Status chips now use
   one documented shape — 12% tint fill, token text, 40% tint border.
5. **Token-level defects.** `--color-navy-800` and `--color-steel-ice` were byte-identical
   in dark (`#241d31`), so SegmentedRow's selected chip vanished; `--color-warning`
   (`#d97706`) had never cleared AA as text in light (2.90–3.18:1); `--color-success`
   (`#047857`) had no budget left for the chip tint (4.45:1).
6. **Modal scrims.** `bg-steel-dark/20|30` followed the ink token, so in dark the overlay
   became a near-white veil that *brightened* the page. New `--color-scrim` token.
7. **UI component boundaries (WCAG 1.4.11).** ToggleRow's off track was `bg-navy-700/30` —
   1.11:1, an invisible pill. Now 3.44 light / 4.08 dark, with a `bg-navy-950` knob at
   3.38 / 5.06 (the old white knob was 2.64:1 on the dark violet accent, 1.42 on amber).
8. **`from-white` in VoiceOverlay's full-screen gradient** — kept the top third of the
   overlay white in dark under a near-white heading. Never reachable by the sweep (the
   overlay is `opacity-0` until listening); caught by reading the source.

## Why

Dark mode is reachable by users and was genuinely broken. The brief scoped the sweep to
grepping two class pairs; five reviewers had already shown that is inadequate, and the
measured sweep confirmed it — the brief's own grep now returns clean while 41 real defect
groups existed.

## Files touched

- `apps/web-client/src/index.css` — new `--color-steel-muted` and `--color-scrim`; dark
  `--color-steel-ice` moved off its collision with `navy-800`; `--color-warning` and
  `--color-success` (light) re-tuned; `.glass-panel` fill/border tokenised. All values
  carry their measured ratios in comments.
- 27 component files under `apps/web-client/src/components/` (see the report for the list).

Shared-seam note: `index.css` is the token layer every component reads. Three token values
moved — `--color-steel-ice` (dark), `--color-warning` (light), `--color-success` (light) —
plus two tokens added. Nothing outside the web client reads them.

## Interfaces / contracts changed

None. Two new CSS custom properties (`--color-steel-muted`, `--color-scrim`), which are
additive.

## Status

done

## Verification

- `cd apps/web-client && npm run build` → PASS (`✓ built in 6.29s`, no TS errors).
- Runtime contrast sweep over the live app: every text-bearing element with full ancestor
  alpha compositing, plus `::placeholder` pseudo-elements (invisible to any DOM walk) and
  SVG icon strokes, plus a component-boundary check on toggle tracks/knobs and the
  segmented-control chip. 1,173 measurements per pass across 15 surfaces, run for
  light/dark × violet/amber/teal/indigo accents.
  - **Before:** 312 failing measurements in light, 593 in dark; worst 1.03:1.
  - **After:** 1 live failing group in light (the brand orb monogram, a documented
    exception measured at 2.75–4.25:1 against the gradient it actually sits on), 0 in dark.
    Everything else remaining is a `disabled` control, which WCAG 1.4.3 exempts.
- Static same-element checker over all 35 `.tsx` files × 2 themes × 5 accents (790
  combinations) to cover surfaces the running app cannot reach with the mock provider.
- The brief's own Step 1 grep now returns only two hits, both inside explanatory comments.

Two measurement traps worth recording, because both silently hid defects:
- Chrome returns `oklab(L a b / α)` for Tailwind v4 opacity modifiers. A parser that only
  understands `rgb()` drops those elements entirely — that alone hid 456 of the
  measurements, including the whole `text-steel/60` ramp.
- After flipping `data-theme`, Chrome can serve stale computed backgrounds until a style
  flush is forced. Measuring both themes inside one task produces mixed-theme readings.

## Next

Three items were measured and deliberately **not** changed because they move visual
identity rather than contrast; each is written up with numbers and a proposed fix in
`.superpowers/sdd/task-17-report.md`:
1. `bg-steel-highlight/10 text-steel-highlight` at light/amber — 4.38:1 across 11 sites.
   Needs the light amber accent darkened one step, which must move the AppearancePanel
   swatch hex in lockstep.
2. The brand orb monogram at 2.75:1 on its top stroke (large text, 3:1 bar).
3. SegmentedRow's selected chip surface at 1.11 dark / 1.13 light — the token collision
   that made it *invisible* is fixed, but the chip-vs-track delta is inherently weak and
   is symmetric across themes.
