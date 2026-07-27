# Settings: Data & privacy panel (export + clear all sessions)

- **Date:** 2026-07-28
- **Track:** 1 Chat (cross-cutting UI — settings dialog)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code (Task 15 of the settings overhaul plan)

## What

Added the final settings panel, `DataPanel` ("Data & privacy"). It does three things:

1. **Backup** — downloads the export bundle from `GET /api/export` via `downloadExport()`.
2. **Safety configuration** — renders the 8-key read-only `locked` block from `GET /api/settings` as status text.
3. **Danger zone** — clears every session/message behind an inline typed confirmation.

Also added `--color-danger` to the semantic status tokens in `index.css`, and wired
`handleDeleteAllSessions` in `App.tsx`.

## Why

Phase B built the backend for export and bulk session deletion; nothing in the UI reached
either. This panel is the only entry point for both, and it holds the plan's only
destructive action.

Three decisions worth recording:

**Export errors are branched, not collapsed.** `downloadExport()` deliberately does not
throw — it returns a discriminated `ExportOutcome`. The three interesting failures have
completely different fixes:

| kind | what is wrong | fix |
|---|---|---|
| `client_token_missing` | `VITE_VIOLET_API_TOKEN` unset in the browser build | set it client-side + restart Vite |
| `server_not_configured` | server has no `VIOLET_API_TOKEN`; endpoint returns 503 | set it server-side + restart the API |
| `unauthorized` | both sides have a token and they disagree | make them match + restart Vite |

Rendering "export failed" for all three would tell a user nothing. `http_error` and
`network_error` are also handled.

**No dead download control.** `client_token_missing` is knowable at render time (the fetch
short-circuits), so in that state the button is not rendered at all — the explanation takes
its place. Same after a 503: the control is removed, because no click could succeed.
`unauthorized` keeps the button (a token can be fixed and retried).

**Export availability feeds the danger zone.** The stated justification for offering
"clear all sessions" is that export is the backup path. When export is unavailable the
danger zone says so explicitly instead of letting the section imply a backup exists.

**The confirmation is inline, not a nested dialog.** `SettingsShell` handles Escape in the
*capture* phase, so it would pre-empt a nested dialog's own Escape handler and close the
whole Settings dialog out from under it. Building the confirmation into the panel body
means there is nothing to nest and Escape keeps one meaning.

**`DataPanel` does not take `PanelProps`.** It writes no preferences, so `values` /
`overridden` / `patchNow` / `patchDebounced` would all be dead props. It receives `locked`
and `onDeleteAllSessions` only.

## Files touched

- `apps/web-client/src/components/settings/panels/DataPanel.tsx` — **new**
- `apps/web-client/src/components/settings/SettingsPanel.tsx` — import + `case "data"`;
  `onDeleteAllSessions` promoted from optional placeholder to required
  `() => Promise<void>`
- `apps/web-client/src/App.tsx` — `handleDeleteAllSessions`, `deleteAllSessions` import,
  prop wiring
- `apps/web-client/src/index.css` — **shared seam**: added `--color-danger` to the
  semantic status block (light `#b91c1c`, dark `#f87171`), with the measured contrast
  numbers recorded in a comment

## Interfaces / contracts changed

- `SettingsPanelProps.onDeleteAllSessions` is now **required** and returns a promise
  (`() => Promise<void>`); it was previously `onDeleteAllSessions?: () => void`, a
  placeholder left by Task 5. `App.tsx` is the only caller.
- New CSS custom property `--color-danger` (both themes).
- No backend change, no new env var. `VITE_VIOLET_API_TOKEN` / `VIOLET_API_TOKEN` were
  already introduced by the export-auth task.

## Status

done

## Verification

**Build** — `cd apps/web-client && npm run build` → `tsc -b && vite build`, `✓ built in
12.65s`, no errors.

**Browser** — Chrome against Vite `127.0.0.1:5173` + `uvicorn 127.0.0.1:8000` with
`LLM_PROVIDER=mock`. Token values used for testing were set in the shell only; the real
`.env` was neither read nor modified.

| Check | Result |
|---|---|
| `client_token_missing` (Vite started with no `VITE_VIOLET_API_TOKEN`) | No download button in the DOM at all — only the explanation. Danger zone showed "Export is unavailable, so there is no backup to fall back on." |
| `unauthorized` (Vite with `deliberately-wrong-token`, server with the real one) | 401 → `role="alert"`: "Export was rejected… Make VITE_VIOLET_API_TOKEN identical to the server's VIOLET_API_TOKEN…". Button stayed available for retry. |
| `server_not_configured` (server restarted with `VIOLET_API_TOKEN=`) | 503 → download control **removed**, "Export is disabled on the server… No change in the browser will help." Danger zone flipped back to the no-backup copy. |
| Success (both tokens matching) | "Downloaded violet-export-20260727-193948.json" — filename came from `Content-Disposition`, confirming the CORS expose-header fix works cross-origin. |
| Export file contents | 41 818 bytes on disk. `sessions: 30`, `messages: 111`, `memories: 2`, `preferences.overridden: [ui_mode, theme]`. Zero occurrences of `api_key`, `base_url`, `password`, `token`, `secret`. Top-level keys contain no `locked` block. |
| Safety block | All 8 flags rendered with friendly labels; the section contains **0** buttons/inputs/links. No key, URL, or path shown. |
| Typed confirmation | `delet` → disabled. `Delete` (wrong case) → disabled. `Deletedeletdelete…` → disabled. `delete` → enabled. |
| Clear all sessions | API 30 → 0 sessions; memory candidates 2 → 0; approved memories preserved at 2. Sidebar emptied to "No conversations yet"; chat reset to the empty state with header "New session"; status bar read "Cleared 30 sessions, 111 messages"; the confirmation input reset itself. |
| Memory drawer after clear | "0 pending · 2 approved" / "No pending candidates" — the orphaned candidates are gone, which is why `refreshMemory()` is in the handler. |
| Escape with the confirmation input focused | Closes the whole Settings dialog. Confirms the capture-phase behaviour and that nothing nests. |
| Console | No errors and no warnings for the whole session. |

**Contrast (measured in-page, canvas-resolved sRGB, not eyeballed)** — every string this
panel introduces clears WCAG AA 4.5:1 in **both** themes. The enabled "Clear all sessions"
label measures 5.95:1 light / 5.44:1 dark.

An earlier revision filled the button with `bg-danger/15`; stacked on the section's own
`/5` tint that measured **4.29:1 in dark**, under AA. Changed to a transparent resting
fill with the tint on hover only. No `bg-steel-dark text-white` or `bg-white` +
`text-steel-dark` pairing was introduced anywhere, so Task 17's inventory does not grow.

The one sub-AA string in the panel (`SectionHeader`'s description, `text-steel/70`,
4.42:1 dark) belongs to a shared control used by every panel and predates this task —
left for Task 17.

## Next

- Task 16 integration, Task 17 the dark-mode contrast sweep.
- The dev SQLite database was genuinely emptied by the clear test (30 sessions of prior
  tasks' scratch conversations). Pre-clear copies exist as the exported JSON in the user's
  Downloads folder and a `violet.db` snapshot in this session's scratchpad, if anyone
  wants them back; otherwise both can be deleted.

---

## Fix pass — review findings (same day)

A review of Task 15 found two Important contrast defects the original sweep missed, plus
inaccuracies in `task-15-report.md`'s contrast claims. The export taxonomy, danger-zone
coupling, inline confirmation, and destructive wiring were all verified correct and were
**not** touched.

### What

1. **Confirmation placeholder sub-AA + sole visible instruction.**
   `placeholder:text-steel/50` on the danger-zone confirmation input measured 2.25:1 light /
   3.00:1 dark (real rendered color: steel alpha-blended over `bg-navy-900`, not the nominal
   token value), and there was no visible `<label>` — the placeholder was the only on-screen
   statement of the word that arms an irreversible delete. Fixed two ways: added a real
   `<label>` wired via `useId()`/`htmlFor` (so the instruction survives once the user starts
   typing, which a placeholder cannot), and dropped the placeholder itself to full-opacity
   `placeholder:text-steel` (6.62:1 light / 8.10:1 dark) as a second layer.
2. **`--color-success` failed AA in light mode.** `DataPanel`'s export-success line is the
   token's only consumer anywhere in the codebase (confirmed by grep), so the light value
   had never actually been rendered. Measured 3.46:1 against the page background
   (`--color-navy-950`) / 3.77:1 against the card (`--color-navy-800`) — both fail. Fixed at
   the token in `index.css` (`#059669` → `#047857`, Tailwind emerald-600 → emerald-700),
   not the call site, so every future consumer inherits a passing value. New ratios:
   5.03:1 / 5.48:1 light, dark unchanged at 9.75:1 / 8.43:1 (already fine).
3. **Report correction, no code.** `task-15-report.md` claimed "every string this panel
   introduces clears AA 4.5:1 in both themes." False, per the two items above. Corrected in
   place (append, not silent rewrite) with the root cause: the original sweep used
   `querySelectorAll` + `getComputedStyle`, which cannot see `::placeholder` (not a DOM
   node), and its contrast section was explicitly dark-mode-only, so the light-mode success
   string was never measured. Also corrected concern #3's `SectionHeader` figure, which
   recorded only 4.42:1 dark and omitted 3.67:1 light (the worse, inherited number).

### Why

Both defects share a root cause: the original in-page sweep (`querySelectorAll` +
`getComputedStyle`, dark-mode pass) is structurally blind to `::placeholder` pseudo-elements
and was never re-run in light mode. Neither is a logic defect — both are presentation-only,
which is why the fix path was CSS/markup, and why the export/delete logic underneath
(previously verified) needed no changes.

### Files touched

- `apps/web-client/src/components/settings/panels/DataPanel.tsx` — visible `<label>` for the
  confirmation input (`useId()`-linked), placeholder opacity fix, `aria-label` removed
  (redundant once a real label exists)
- `apps/web-client/src/index.css` — `--color-success` light value `#059669` → `#047857`;
  updated the semantic-token comment block with corrected `--color-warning` figures
  (1.67:1 / 2.77:1, not "~1.5:1") and the new `--color-success` measurements
- `.superpowers/sdd/task-15-report.md` — correction appended under the false claim, concern
  #3 figure corrected, new `## Fix pass` section with full before/after ratios

### Track

1 Chat (same as original — settings dialog)

### Status

done

### Verification

`cd apps/web-client && npm run build` → `tsc -b && vite build`, no TypeScript errors, no
Vite errors, same pre-existing 500 kB chunk-size advisory. No frontend test runner exists
for this package. No backend server started — both fixes are CSS/markup-only and were
verified by direct hex-value contrast computation against the tokens actually in
`index.css`, so `data/violet.db` was never touched. `data/preferences.json` unmodified
(confirmed via `git status`; only `DataPanel.tsx` and `index.css` show as changed pre-commit).

### Next

- Task 17's sweep should add a `::placeholder`-aware check (can't be done via
  `getComputedStyle` on the input itself; needs either a manual pass or reading the
  stylesheet rule directly) and should run its contrast pass in both themes, not dark-only,
  to avoid repeating this exact miss.

---

## Task 16 — persist persona and provider selections (same file, new day's work continues)

- **Date:** 2026-07-28
- **Track:** 1 Chat (same file as Tasks 11–15)
- **Branch:** feat/settings-overhaul

### What

`default_personality` / `default_provider` have been editable preference keys since Task 1,
and the persona/provider pickers have rendered since Task 5, but selecting either only ever
set local React state — both reset on every reload. Wired both to persist:

1. **Bootstrap seed.** `App.tsx`'s `fetchSettings()` bootstrap now reads
   `settings.values.default_personality` / `default_provider` and seeds `personalityId` /
   `selectedProvider` from them, once, at mount.
2. **Persist on selection.** `SettingsPanel`'s `onSelectPersonality` / `onSelectProvider`
   handlers (passed from `App.tsx`) now call `setPersonalityId`/`setSelectedProvider` **and**
   `handlePatchSettings({ default_personality: id })` / `{ default_provider: id }` in the same
   click — `patchNow`, not `patchDebounced` (see rationale below).
3. **Race-safe fallback guards.** The existing personalities-bootstrap guard (falls back to
   the first available profile if the current id doesn't resolve) and a newly added provider
   equivalent were rewritten as functional `setState` updaters instead of reading the
   `personalityId`/`selectedProvider` closed over at mount — see "Ordering hazard" below.
4. `selectedAgent` / `onSelectAgent` untouched — no persistence key added, per the brief
   (delegation is deliberately session-local).

### Why — real line numbers (brief's were stale)

The brief (`task-16-brief.md`) cited `App.tsx:83/193/204-206`, written before Tasks 11–15
extracted panels and added appearance/speech-output/delete-all wiring. Actual locations at
the start of this task (HEAD `929ec8e`):

- `personalityId` hardcoded init: line 107 (`useState("violet.default")`) — left unchanged,
  it's just the pre-seed placeholder.
- Personalities/providers bootstrap (the `Promise.all([...]).then(...)`) with the
  fallback guard and the unconditional `setSelectedProvider(providerResponse.active)`:
  lines 212–249, override at line 228.
- `fetchSettings()` bootstrap to modify: lines 239–241.
- `SettingsPanel` instantiation with `onSelectPersonality={setPersonalityId}` /
  `onSelectProvider={setSelectedProvider}`: lines 794 / 797 (inside 789–816).

### Ordering hazard (not in the brief, found while implementing)

The `Promise.all(...)` bootstrap and the separate `fetchSettings()` call both live in the
same `useEffect(() => {...}, [])`, fired as sibling un-awaited promise chains in one mount.
Which resolves first is a network race. The brief's Step 1 snippet seeds `personalityId` /
`selectedProvider` inside the `fetchSettings()` branch; the existing fallback guard (and the
provider equivalent this task adds) lives in the *other* branch and originally read
`personalityId` via the closure captured at mount — i.e., always the hardcoded
`"violet.default"`, **never** whatever the `fetchSettings()` branch had since-set, regardless
of which request actually won the race (the effect callback itself only runs once and
doesn't see intervening renders). Concretely: `nextPersonalities.some(p => p.id ===
personalityId)` would keep checking against `"violet.default"` forever, which is present in
`nextPersonalities` in the common case — so the guard would silently report "fine" even when
the seeded `personalityId` state was an id that no longer resolves. That's exactly the
hazard the brief calls out ("verify the guard still runs after this change... it must
compare against whatever `setPersonalityId` ended up with").

Fixed by switching both guards to the functional updater form —
`setPersonalityId((current) => ...)` / `setSelectedProvider((current) => ...)` — which always
reads the true current state at the moment it runs, independent of promise-resolution order.
Also added the provider-side equivalent (`providerResponse.items.some(item => item.id ===
current) ? current : providerResponse.active`), since the brief notes the identical
reasoning applies to a stored provider that's no longer offered, but the pre-existing code
had no such guard for providers at all (only the unconditional override this task removes).

### Seeding approach vs. the Task 14 `speechOutputSeededRef` pattern

Deliberately **not** reused. Task 14's `speechOutputTappedRef` guards a recurring
`useEffect(() => {...}, [appSettings])` that re-derives local state from `values.auto_speak`
on *every* settings change, because the composer's speak-toggle button can diverge from the
persisted value **without ever patching it** — so blind resyncing would erase a legitimate,
un-persisted local choice, and the ref exists to detect and protect that divergence.

Persona/provider have no such divergence path: the only two things that ever write
`personalityId`/`selectedProvider` after mount are (a) the click handlers, which now always
patch immediately in the same call, keeping local state and `appSettings.values` in lockstep,
and (b) the fallback guards, which correct an *invalid* id locally without patching it back
(intentionally — the brief requires the fallback to just work, not to silently overwrite the
user's stored preference). A recurring `[appSettings]` resync would actively fight (b): any
unrelated settings change after a fallback correction would re-read the still-stale, still-
invalid `values.default_personality` and stomp the correction right back. So this task uses
a **one-time** seed inside the `fetchSettings()` bootstrap only (matching the brief's Step 1
snippet as given), not a recurring effect — the opposite of Task 14's fix, applied
deliberately because the two cases differ in exactly the property that made Task 14's ref
necessary.

One accepted gap from this choice: `GeneralPanel`'s "Reset section" resets both
`default_personality` and `default_provider` server-side (both are in the backend's
`"general"` preference group, confirmed in `preferences/store.py`) via `onSettingsRefreshed`,
which updates `appSettings` directly and does not touch `personalityId`/`selectedProvider`.
A reset while Settings is open would leave the picker showing the old selection until the
next reload (which re-seeds correctly from the now-reset `default_personality`/
`default_provider`). Not covered by the brief's four browser checks; noted here rather than
silently fixed, since fixing it would require either threading a signal through
`onSettingsRefreshed` or reintroducing the resync-effect this task deliberately avoided.

### Files touched

- `apps/web-client/src/App.tsx` — bootstrap seeding, functional-updater fallback guards
  (personality + new provider guard), `onSelectPersonality`/`onSelectProvider` now persist

### Status

done

### Verification

**Build** — `cd apps/web-client && npm run build` → `tsc -b && vite build`, `✓ built in
17.39s`, no TypeScript errors. Same pre-existing "chunk larger than 500 kB" advisory as
prior tasks, unrelated.

**Browser** — Vite `127.0.0.1:5173` + `uvicorn` on `127.0.0.1:8000`, isolated with
`DATABASE_URL=sqlite:///./.tmp/task16-scratch/scratch.db`, `MEMORY_DIR=./.tmp/task16-scratch/memory`,
`LLM_PROVIDER=mock` (real `.env`/`data/violet.db` never touched or read for chat data).

| Check | Result |
|---|---|
| Select "Devoted Strategist" persona | `PATCH /api/settings` fired in the same network batch as the click (no debounce gap); response `values.default_personality: "violet.devoted_strategist"`. Reload → still selected in Settings; header/composer/empty-state assistant name still reads "Violet" (both profiles' `name` field is literally `"Violet"` — codename differs, display name doesn't — so this check is satisfied but not a strong discriminator). |
| Select "Local / OpenAI-compatible" provider (Model tab) | `PATCH /api/settings` fired immediately; response `values.default_provider: "openai_compatible"`, `overridden` grew to include it. Reload → composer chip reads "Local" (`shortProviderLabel("openai_compatible")`), matching the persisted choice. |
| Timing | Both PATCHes appear back-to-back with the preceding `GET`s in the captured network log (sub-frame gap, not a separate ~300 ms-later request) — consistent with `patchNow` or wired directly, not through the debouncer. |
| Fallback: renamed `configs/personality/violet.devoted_strategist.json` → `.json.bak`, restarted backend | `/health` reported `personality_profiles: ["violet.default"]` only. Reload with `preferences.json` still holding the stale `default_personality` → Settings → General showed a single "Violet" button, selected, no empty/broken state. File restored immediately after (`mv` back), backend restarted again, `/health` confirmed both profiles present again before continuing. |
| Agent selection not persisted | Selected "Analyst" under Settings → Agents (dev mode). Reloaded. Settings → Agents showed "Violet (no delegation)" selected again — confirms `selectedAgent` correctly stays session-local. |

**Cleanup** — backend and Vite dev server stopped; `.tmp/task16-scratch` (gitignored) removed;
`data/preferences.json` restored to exactly `{"ui_mode": "developer"}` (it had accumulated
`default_personality`/`default_provider` from the manual test clicks, since the backend's
`PreferencesStore` path is fixed at `repo_root/data/preferences.json` regardless of
`DATABASE_URL` — confirmed via `git status` showing only `App.tsx` modified afterward).
`configs/personality/` restored to its original two files. Real `.env` and `data/violet.db`
were never opened or modified.

### Next

- Task 17's contrast sweep (no new color classes were introduced by this task — purely
  behavioral wiring, no forbidden `bg-steel-dark text-white` / `bg-white`+`text-steel-dark`
  pairs added).
- Possible future cleanup: the "general reset desyncs picker until reload" gap noted above,
  if it ever proves user-visible enough to matter.
