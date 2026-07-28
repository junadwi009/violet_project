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

---

# Fix pass — review findings (same day)

- **Date:** 2026-07-28
- **Track:** cross-cutting (web-client theme)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code

## What

Six review items against the sweep above. One was a genuine new defect introduced by the
sweep itself; the rest were wrong or overstated claims in the write-up, plus judgement calls
to record.

1. **New dark-mode AA failure, introduced by this branch — fixed.** Moving dark
   `--color-steel-ice` from `#241d31` to `#2c2440` (to break its collision with `navy-800`)
   made the ice tint the worst surface a status chip can land on. `SkillLab`'s `Verdict`
   chips render inside a `p-3 rounded-xl bg-steel-ice` wrapper (`SkillLab.tsx:219`), and
   `bg-danger/12 text-danger` at 11px measured **4.44:1** there — under AA, and reachable
   (`redundant` and `low_quality` both map to `BAD_CHIP`). Fixed by nudging dark
   `--color-danger` `#f87171` → `#fb8a8a`: **4.44 → 5.14** in that exact nesting. The
   §3.5 blast-radius check had re-measured only the three plain ink tokens on `steel-ice`,
   never the chips.
2. **"Dark: no live failure at all" was an artifact — claim corrected.** The orb gradient
   and its `text-white` monogram are theme-independent, so the ~2.87:1 top-stroke reading
   applies in dark exactly as in light. The dark sweep reported zero only because the same
   sibling-gradient blindness that yields a spurious 1.09:1 in light yields a spurious
   ~18.7:1 in dark. Dark has the **same one** deferred sub-threshold group as light.
3. **The "lockstep" justification for deferring the accent fix was wrong — withdrawn.**
   `AppearancePanel.tsx:23-26` states the swatches "do NOT match the token actually
   applied", and teal already diverges three ways (swatch `#0d9488`, light `#0f766e`, dark
   `#2dd4bf`). Nudging light amber needs no swatch edit. Deferral kept on the other reason
   (certified brand table, identity decision).
4. **Inverted code comment — fixed.** The sweep's mechanical class substitution rewrote
   `DataPanel.tsx:299` from `text-white` to `text-navy-950`, inverting the sentence: a
   comment was edited as if it were markup. `text-navy-950` on a danger fill is 5.94 light /
   8.12 dark and is what `MemoryDrawer`/`VoiceOverlay` ship. The commit was audited for the
   same class of error — this was the only one.
5. **`.glass-panel` "light mode is byte-identical" — overstated, corrected.** True of the
   fill (`navy-800` is `#ffffff`); not of the border, which went from `rgba(255,255,255,0.5)`
   to `navy-700/50` (`#ded5e8` at 50%) — a faint lavender hairline where there was an
   invisible white one.
6. **Recorded, not fixed:** `ToggleRow`'s weaker at-a-glance on/off read (off-vs-on track now
   1.24–2.22:1, though 1.4.11 is met on presence at 3.69 light / 4.37 dark);
   `hover:opacity-90` on solid danger at 4.44:1 light/violet; `DataPanel`'s clear-sessions
   hover at 4.32:1 dark pre-nudge (already anticipated in that file's own comment);
   `ToolTrace`'s three-step text hierarchy collapsed to one; and the pre-existing sidebar
   accent figures (light amber 4.22, light teal 4.60 against the quoted 4.61/5.02).

## Why

Item 1 is a defect created by the very commit whose purpose is dark-mode AA, so it gates the
same merge the sweep was gating. Items 2–5 are accuracy: the report is the artifact the next
person trusts, and a "dark is perfectly clean" headline plus a fabricated coupling constraint
would both mislead — one into under-testing dark, the other into over-pricing a one-line fix.

## Files touched

- `apps/web-client/src/index.css` — dark `--color-danger` `#f87171` → `#fb8a8a`; token notes
  corrected (the stale pre-move "danger … 4.89 dark"; the card-as-worst-surface framing,
  which is what let the ice-tint failure through; the `text-white` line that mislabelled two
  *dark* values as "(light) and (dark)"); `.glass-panel` fill-vs-border claim corrected; a
  new note that a 12% danger chip on the light sidebar is 4.43 and has no live site today.
- `apps/web-client/src/components/settings/panels/DataPanel.tsx` — comment restored to
  `text-white`, with a note on why it moved.
- `.superpowers/sdd/task-17-report.md` — §2 and §5.1 annotated in place (struck, not
  rewritten); new `## Fix pass` section with the full danger-token surface set.

Shared-seam note: one more token value moved — `--color-danger` (dark only). ~~Lightening is
monotone for every way this token is used (it raises both the tinted-chip ratios and the
dark ink on the solid fill), so no danger surface regresses~~; the full 13-row surface set is
in the report. Nothing outside the web client reads it.

> **Correction (2026-07-28, final fix pass).** The struck sentence is retracted. Commit
> `877ff90` was written specifically to narrow it and never updated this log, which left the
> owning entry asserting something `index.css` had already stopped claiming.
>
> Monotone for every danger-**coloured** foreground — tinted chips, plain text, and the dark
> ink on the solid fill all rise, +0.70 to +1.35. **Not** monotone for a danger-**tinted
> container holding non-danger text**: a lighter tint lightens the background, so the
> near-white `text-steel-dark` inside it loses contrast. Two measured drops:
>
> | surface | before | after |
> |---|---|---|
> | danger-zone body copy on `bg-danger/5` | 13.08 | 12.96 |
> | export-error detail on `bg-danger/10` | 12.04 | 11.75 |
>
> Immaterial against a 4.5 bar, but the direction is real, and this note is what the next
> token move gets checked against. The failure pattern is the one named in `877ff90`:
> asserting a worst case instead of enumerating it — the same shape of claim that let the
> `--color-steel-ice` move ship a regression in the commit meant to remove them.
>
> `877ff90` also breached this project's update-log rule: it changed `index.css` with no log
> entry at all. Recorded here and in
> `logs/settings-clear-and-knowledge-error-surfaces_2026-07-28_log.md`.

## Interfaces / contracts changed

None.

## Status

done

## Verification

- `cd apps/web-client && npm run build` → PASS, no TS errors.
- Independent re-measurement, deliberately not reusing the original harness:
  - Colours resolved by **Chrome itself** — Canvas 2D `fillStyle` + `fillRect` +
    `getImageData` — so Tailwind v4's `color-mix(in oklab, …)` is the engine's problem, not
    a parser's. Verified exact: `oklab(0.442241 0.0327968 -0.0491156)` → `#5a4b6e`
    (`--color-steel`).
  - Unparseable strings **detected via sentinel-compare**, not dropped: `fillStyle` is
    seeded with two different sentinels before each assignment. **310 measurements,
    0 parse failures** (the first attempt's parser had silently dropped 456 of 1,173).
  - `opacity` is composited, not just flagged, so `hover:opacity-90` is measurable.
  - Every fixture reproduces the **nesting copied verbatim from the component**, since
    measuring the token in isolation is exactly what missed item 1.
  - Run against the **built** CSS bundle served from `dist/`, over both themes × all five
    accents. Only remaining sub-threshold row is the sidebar danger chip, which has no live
    call site and is now documented in `index.css`.

Two measurement traps, one new:
- The theme-flip trap is worse than a reflow: after stamping `data-theme`, element-level
  computed values stay stale even after a forced reflow — a task/frame boundary must be
  crossed first.
- **New:** a backgrounded tab throttles `requestAnimationFrame` to never and skips style
  recalc, so a frame-only wait either hangs (a 45s CDP timeout was observed) or returns
  **empty** computed values that a harness will score as null rather than as an error. Frame
  waits are now raced against a timer and every pass polls until style resolution has
  demonstrably run.
- Tailwind emits only the classes it sees in source, so `opacity-90` and
  `bg-[color:var(--color-danger)]/15` exist only behind `hover:`. Hover states measured via
  the bare class silently return the rest-state number; inline styles were used instead.

Data safety: `data/violet.db` was never opened — no server was started in this pass.
`data/preferences.json` backed up by copying the real file and restored from that copy,
verified by checksum.

## Next

Unchanged from the sweep, minus the corrected reasoning:
1. The three accent nudges (light amber `#92400e`, light teal `#115e59`, dark indigo
   `#a5b4fc`) — a brand-identity decision, **not** a two-file swatch-lockstep change as
   previously claimed. One line each in `index.css`.
2. The brand orb monogram — now correctly recorded as sub-threshold in **both** themes.
3. SegmentedRow's selected chip surface (1.11 dark / 1.13 light), symmetric across themes.
4. Optional: revisit `ToggleRow`'s off-track value so on/off reads at a glance again, and
   `ToolTrace`'s collapsed text hierarchy — both conformant, both worse than before.
