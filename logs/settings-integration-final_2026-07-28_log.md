# Settings overhaul — Phase E integration verification (Tasks 16–18)

- **Date:** 2026-07-28
- **Track:** cross-cutting (web client settings + assistant-core preferences)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code

## What

Closing pass on the 18-task settings overhaul. Covers Task 16 (persona/provider
persistence and the bootstrap ordering race), Task 17 (the two-theme AA contrast
sweep), and Task 18 (this end-to-end verification).

Task 18 was scoped as verification, not features. It found one genuine defect that
per-task review could not have caught, because it lives in the seam between App and
the settings dialog rather than inside either: **a failed preference write reported
itself only in `WorkspaceHeader`'s status pill, which the settings scrim covers and
blurs.** That is fixed here. Everything else in the walkthrough passed as built.

### Tasks 16 and 17, as they landed

- **Task 16** (`49f1a4d`, then `dc96bb8`): persona and provider now persist across a
  reload. The follow-up commit removed a bootstrap ordering race — seeding from
  `/api/settings` and validating against `/api/personalities` / `/api/providers` were
  two sibling promise chains whose interleaving decided whether a stored id naming a
  profile the server no longer offers survived into app state. They are now one
  ordered step inside a single `Promise.all`, plus a one-shot resync on group reset.
- **Task 17** (`c85c13d`, `3658f45`, `929ec8e`, narrowed by `877ff90`): swept both
  themes for AA failures **by measuring computed colours in a browser**, not by
  grepping class names. Headline fix was `text-white` on token-driven fills computing
  1.16:1 white-on-white in dark mode. `877ff90` exists because the original write-up
  over-claimed danger-token monotonicity; it narrows the claim to what was measured.
  That correction is the reason this log states figures rather than adjectives.

### Task 18 fix — write failures now surface inside the dialog

`App.handlePatchSettings` caught its own error and called `setStatus({tone:"error"})`.
`SettingsShell` already has an `error` slot, but only `SettingsPanel.handleReset` ever
fed it. So an ordinary preference write failing — by far the more common case — was
reported at (1121, 20) in the workspace header, underneath a `fixed inset-0 ...
backdrop-blur-sm z-50` scrim. Measured: `document.elementFromPoint` at the pill's
centre returned the scrim, and the dialog contained zero `[role=alert]` nodes.

Fix: App keeps a `settingsError` alongside `status`, cleared on a successful write and
on every entry into Settings (all three `onOpenSettings` call sites now route through
one `openSettings()`), and passes it as `patchError`. `SettingsPanel` renders
`error ?? patchError` into the shell's existing error slot — reset failures still win,
being the more deliberate action. Deliberately **not** a rethrow: two of the three
`handlePatchSettings` call sites invoke it without awaiting, so rejecting would turn
every failed persona/provider click into an unhandled rejection.

## Why

Per-task review signs off one task against one brief. It structurally cannot see
interactions between tasks, or a regression introduced after the task that owned that
code was already approved. This pass exists to look at the whole feature at once, and
it earned its keep exactly once — on the error-feedback seam above.

## Files touched

- `apps/web-client/src/App.tsx` — `settingsError` state; `handlePatchSettings` sets and
  clears it; new `openSettings()` used by all three entry points; `patchError` prop.
- `apps/web-client/src/components/settings/SettingsPanel.tsx` — accepts `patchError`,
  renders `error ?? patchError` into the shell's error slot. **Shared seam.**
- `logs/settings-integration-final_2026-07-28_log.md` — this file.

## Interfaces / contracts changed

`SettingsPanelProps` gains a required `patchError: string | null`. No backend, schema,
or env-var change. `PanelProps` (`patchNow` / `patchDebounced`) is untouched — the two
write channels keep their existing `void` signatures.

## Status

done.

## Verification

Backend: **`python -m pytest -q` → 306 passed, 237 warnings in 70.29s**, run from the
repo root with the system interpreter (`C:/Users/arjuna.putranto/anaconda3/python.exe`).
The repo `.venv` lacks `httpx` and `pytest-asyncio` and was not modified. 306 both
before and after the change, matching the Task 13 baseline — the fix is frontend-only.

Frontend: **`npm run build` → `✓ built in 10.10s`**, `tsc -b` clean. Output
`index-*.js` 505.55 kB (gzip 160.98 kB), `index-*.css` 81.78 kB (gzip 24.54 kB). The
one warning is the pre-existing >500 kB chunk-size advisory, not an error.

Walkthrough run against `LLM_PROVIDER=mock`, assistant-core on 8000, Vite dev on 5173
and `vite preview` on 4173, viewport 1280×720. Where a claim is a measurement, the
measurement is given.

1. **Settings opens; dev-only tabs gated — PASS.** Developer mode renders 9 tabs
   (General, Appearance, Behavior, Voice, Knowledge, Skills, Data & privacy, then Model
   and Agents under a `dev` divider). Clicking **User** re-renders exactly 7, divider
   gone, Model and Agents absent from the DOM — not merely hidden.
2. **Escape / focus / arrow keys — PASS, asserted on `document.activeElement`.** On
   open, focus lands on `#settings-tab-general`. ArrowDown → `#settings-tab-appearance`;
   End → `#settings-tab-agents`; ArrowDown wraps → `#settings-tab-general`; ArrowUp
   wraps back → `#settings-tab-agents`. `aria-selected` follows focus. Escape closes
   the dialog and `document.activeElement === trigger` is **true by object identity**,
   not by matching a label.
3. **Dark theme, no flash on first paint — PASS, on the production build.** On a fresh
   dark load every structural surface is dark; the only light-background elements are
   the `bg-steel-dark` avatar badge (an intentional inverted chip with `text-navy-950`)
   and the `bg-steel-highlight` accent bars. First-paint evidence from `vite preview`
   on 4173 with dark cached: `domInteractive` **52.1 ms**, `first-paint` and
   `first-contentful-paint` both **296.0 ms**, stylesheet complete at 71.3 ms, and
   `<body>` background `rgb(20, 16, 28)`. The synchronous theme script sits in `<head>`
   of the built `dist/index.html` ahead of the deferred module script, and `#root` ships
   empty — so nothing can be painted before the theme is stamped, ~244 ms earlier.
   - *Correction recorded on purpose:* an earlier measurement in this session appeared
     to show large surfaces keeping the previous theme's colour after a live flip. That
     was an artifact of the browser pane being hidden — `document.visibilityState`
     `"hidden"` and **0 rAF frames in 800 ms**, so in-flight CSS transitions never
     advanced and `getComputedStyle` returned the frozen start value. A flip performed
     with a real click while the pane was compositing inverted correctly. Not a defect;
     noted so the false positive is not rediscovered later.
4. **Debounced vs immediate write channels — PASS, from a network log.** Font-size drag:
   11 `input` events over 184.5 ms → **0 PATCH during the drag, exactly 1 after**
   (`{"font_scale":1.15}`). Temperature drag: 9 steps → **exactly 1 PATCH**
   (`{"temperature":1}`). Timers were verified un-throttled (11×16 ms slept 184.5 ms).
   Immediate channel, measured click→`fetch` latency: accent swatch **0.2 ms**
   (`{"accent":"teal"}`), density segmented **0.1 ms** (`{"ui_density":"compact"}`),
   Behavior toggle **0.2 ms** (`{"web_search_enabled":true}`), Mode segmented **0.2 ms**
   from a real pointer click. One PATCH each. Rate + Pitch changed inside one window
   coalesced into a single `{"voice_rate":1.6,"voice_pitch":0.7}`, confirming the one
   dialog-wide debouncer.
5. **Persona and provider survive a reload — PASS.** Set to Devoted Strategist /
   Local · OpenAI-compatible, full reload: server `default_personality`
   `violet.devoted_strategist`, `default_provider` `openai_compatible`; the panel shows
   both as selected and the composer chip reads "Local".
6. **Voice test uses the configured rate — PASS.** Audio cannot be captured here, so
   `speechSynthesis.speak` was instrumented and the assertion is on the utterance:
   one call, `SpeechSynthesisUtterance` with `rate 1.600000023841858`,
   `pitch 0.699999988079071`, `lang "id-ID"`, text "Halo, saya Violet. Ini contoh suara
   saya." — matching the configured values.
7. **Export — PASS in both configurations.** With `VITE_VIOLET_API_TOKEN` set (a
   temporary `apps/web-client/.env.local`, since removed): clicking Export produced a
   42,015-byte `application/json` blob named `violet-export-20260728-021042.json` with
   30 sessions / 111 messages / 2 memories / preferences, and the panel reported
   "Downloaded …". The anchor click was intercepted so nothing was written to disk.
   Secrets: the payload was scanned against every value in the real `.env` —
   `VIOLET_API_TOKEN`, `JWT_SECRET`, `OPENROUTER_API_KEY`, `LLM_BASE_URL`,
   `OPENROUTER_BASE_URL`, `DATABASE_URL` **all absent**, zero secret-shaped key names,
   and the `locked` safety block excluded. `/api/export` returns 401 with no token and
   401 with a wrong token. Without a client token the panel renders **no download
   control at all** — just the amber block naming `VITE_VIOLET_API_TOKEN`, the file to
   set it in, and the restart needed; the danger zone additionally states that export is
   unavailable so there is no backup.
8. **Reset section — PASS.** Behavior with `web_search_enabled` overridden: dot present,
   button enabled. One `POST /api/settings/reset {"group":"behavior"}` removed exactly
   `web_search_enabled` from `overridden` (`ui_mode`, `font_scale`, `accent`,
   `ui_density`, `temperature` untouched), restored the value to `false`, cleared the
   dot and disabled the button.
9. **Backend down → error inside the modal — FAILED as built, FIXED, now PASS.**
   Before: PATCH threw `TypeError: Failed to fetch`, the dialog contained **zero**
   `[role=alert]` nodes, and the only report was the header pill at (1121, 20) with the
   scrim as the topmost element at its centre. After the fix: a single `role="alert"`
   renders **inside** the dialog at (126, 125, 1029×38), fully within the dialog box and
   topmost at its own centre. It clears on the next successful write and on reopen.

**Destructive path — gating verified, deletion not executed.** `data/violet.db` (30
sessions / 111 messages) was never cleared. The confirm input was driven through
`""`, `delet`, `Delete`, `DELETE`, `delete `, ` delete`, `deletee` — button `disabled`
in every case — and enabled only on exactly `delete`. The button was never clicked and
the field was left empty.

### Layout — first time anyone has looked

Nothing in tasks 1–17 examined layout; screenshots only became available late. Captured
and inspected every settings panel in both themes at 1280×720 on the production build,
alongside a programmatic audit (scrollWidth vs clientWidth, painted bounds vs the dialog
box, nav and panel scroll extents).

Clean: **no horizontal overflow anywhere** (`documentElement.scrollWidth ==
clientWidth` on every panel), no text or control wider than its box, the nav rail never
scrolls (541 px of items in 541 px), the dialog never leaves the viewport, and the
light/dark pairs are structurally identical. Every "outside the dialog" hit the audit
raised was ordinary vertical scrolling inside `[role=tabpanel]`'s `overflow-y: auto`.

Four things are ugly rather than broken. None was fixed here — they are cosmetic, and
this task is meant to end the plan, not extend it:

1. **Tab switches keep the previous panel's scroll offset.** `[role=tabpanel]` is one
   persistent node whose children swap, so scrolling Agents to 400 px and clicking Model
   opens Model at `scrollTop 400` — heading and "Reset section" off-screen. It only
   resets when you pass through a panel short enough for the browser to clamp it. The
   most annoying of the four.
2. **Voice overflows by 30 px at a 720 px-tall window** (`scrollHeight` 571 vs
   `clientHeight` 541), so "Test voice" — the panel's primary action — is sliced by the
   dialog's bottom edge in both themes. Fits at 900 px.
3. **The Skills list is pinned to `max-h-40`** regardless of available space: 12 items,
   744 px of content, in a 184 px window, with roughly 210 px of the panel left empty
   below the button, and the third card sliced mid-row at the fold. Agents, the other
   list panel, has no cap at all — the two are inconsistent.
4. **Toggle labels do not align.** `ToggleRow` renders its optional icon inline without
   reserving a column, so on Behavior "Web search" starts at x=392 while "Canvas mode"
   and "Ask before saving memory" start at x=370 — a 22 px stagger inside one card.

Also cosmetic: the export guidance breaks mid-path across lines ("apps/web-" /
"client/.env.local"), and General/Appearance/Behavior leave a large empty area because
the dialog is a fixed `min(85vh, 42rem)` regardless of content.

Coverage limit, stated plainly: 1280×720 only. Resizing the browser pane reliably broke
its compositing, so narrow and tall viewports were **not** examined. Responsive
behaviour below ~1000 px remains unverified.

### Environment restored

`data/preferences.json` reads exactly `{"ui_mode": "developer"}`, restored from a copy
of the original taken before any interaction. The real `.env` was never modified; the
temporary `apps/web-client/.env.local` was deleted. Dev, preview, and API servers were
stopped and ports 5173 / 4173 / 8000 confirmed free.

Two `Received NaN for the value attribute` React warnings on first paint were ignored
per the task brief — a standing item investigated across three tasks and unrelated.

## Next

Nothing blocking. Optional follow-ups, in the order they would be worth doing:

1. Reset `[role=tabpanel]`'s `scrollTop` on tab change (layout item 1) — one line, and
   the only one of the four that actively hides a control.
2. Let the Skills list grow into the panel instead of `max-h-40`, or cap Agents the same
   way, so the two list panels agree (item 3).
3. Give `ToggleRow` a fixed icon column so labels align (item 4).
4. Verify the dialog below ~1000 px wide on a browser that can be resized.
