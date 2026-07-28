# Clear-sessions and Knowledge error surfaces inside the settings dialog

- **Date:** 2026-07-28
- **Track:** cross-cutting (1 Chat state + 2 RAG controls, both via the settings UI)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Opus 5

## What

Three pre-merge fixes from the whole-branch review of the settings overhaul.

1. **Both outcomes of an irreversible clear are now reported inside the settings dialog.**
   `handleDeleteAllSessions` was routing success *and* failure to `setStatus`, i.e. the
   `WorkspaceHeader` status pill, which sits underneath the settings scrim. It returned
   `Promise<void>` and always resolved, so `DataPanel` could only flip `clearing` back to
   false — on failure the button re-enabled, `"delete"` was still in the confirm field, and
   nothing was said. Same treatment applied to `KnowledgePanel`, which had **no** error
   surface at all (`grep -nE 'role="alert"|error|catch'` returned zero hits): reindex, full
   rebuild, and Google Drive connect/disconnect were all silent in exactly the same way.
2. **Endpoint-level locked-key rejection test.** The branch's central security claim was
   pinned only at the store. Added `PATCH /api/settings {"allow_shell_tools": true}` → 422
   at the route.
3. **Corrected a retracted claim that survived in a log.** Commit `877ff90` narrowed
   `index.css`'s danger-token monotonicity note to what was actually measured, but never
   touched the log that owned the claim.

## Why

### 1 — the class Task 18 fixed only one member of

Task 18 added a `patchError` prop so failed preference writes render inside the modal, and
measured the underlying problem: zero `[role=alert]` inside the dialog, and
`document.elementFromPoint` at the status pill returning the scrim. That measurement was
re-run here before any change and reproduced exactly (pill at (1186, 17), topmost element
`fixed inset-0 bg-[color:var(--color-scrim)]/30 backdrop-blur-sm z-50`).

The clear path was the worst remaining member of that class, because it is *irreversible*
and because its failure mode was indistinguishable from a click that did nothing.

### Design choice: `onDeleteAllSessions` now rejects and resolves with the report

Three shapes were available, and the branch already contains two of them:

- **A prop that carries the error** (Task 18's `patchError`). Chosen there because two of
  `handlePatchSettings`' three call sites invoke it *without awaiting*, so rethrowing would
  produce unhandled rejections. **Does not apply here** — `onDeleteAllSessions` has exactly
  one call site (`DataPanel`'s button handler) and it already awaits inside `try/finally`.
- **A result object / discriminated union** (`downloadExport`). Chosen there because export
  failures have genuinely different *fixes* — `client_token_missing` vs
  `server_not_configured` vs `unauthorized` — and a thrown `Error` cannot carry that
  taxonomy without a subclass; `requestJson`'s throw convention was the awkward part.
  **Does not apply here** — a failed clear has no taxonomy. It is one message.
- **Reject, i.e. `requestJson`'s own convention**, which every other handler in `App.tsx`
  already follows. Nothing argues against it here, and it needs no new type.

So: reject on failure. The other half of the decision is the *success* shape — a
`Promise<void>` cannot carry `deleted_sessions` / `deleted_messages` to the panel, so the
handler now returns the `DeleteReport` it already had in hand. `setStatus` is still called
on both paths: the pill is the right surface once Settings is closed, it just cannot be the
*only* one. The same reasoning was applied to `handleReindex` (returns `ReindexReport`) and
`handleConnectGDrive` / `handleDisconnectGDrive` (return `void`, reject on failure) — each
also has exactly one call site, which awaits.

`KnowledgePanel` funnels all four actions through one `run(verb, action)` wrapper so none of
them can quietly regrow a swallowed failure, and reports per-document reindex errors, which
arrive *inside* a 200 response and were previously dropped on the floor.

### Contrast: no new surface was invented

Neither panel adds a tinted container. The DataPanel comment already records that stacking a
15% danger tint on the danger zone's own 5% drops danger-coloured text to 4.29:1 in dark, so
a nested box would have been a new, unmeasured surface. Both results render directly on the
surface their section already owns. Measured in-browser (Canvas-resolved, the Task 17
method), **both themes**:

| surface | foreground | light | dark |
|---|---|---|---|
| `bg-danger/5` (danger zone) | `--color-danger` | 5.92 | 6.46 |
| `bg-danger/5` (danger zone) | `text-steel-dark` | 16.39 | 12.89 |
| `bg-danger/5` (danger zone) | `--color-success` (Check icon) | 7.03 | 7.76 |
| `bg-steel-ice` (knowledge card) | `--color-danger` | — | 6.35 |

The 6.35 is *exactly* index.css's recorded "danger plain on steel-ice" figure, which is a
useful cross-check on the harness. Note the button comment above it quotes 5.47 dark for
danger on `bg-danger/5`; that figure predates commit `3658f45` lightening the dark danger
token, and 6.46 is the post-move value. Zero new dark-mode failures; no `bg-steel-dark
text-white` or `bg-white`+`text-steel-dark` introduced.

One thing the review did not ask for was added: a `scrollIntoView({ block: "nearest" })` on
each result. The danger zone and the reindex row both sit near the bottom of a scrolling
panel, and a result rendered below the fold is only marginally better than one behind the
scrim. Verified by scrolling the panel to the top before clicking and confirming the panel
scrolls itself (`scrollTop` 0 → 115.2) so the message is fully inside the scroller.

### 2 — the security claim deserved a route-level pin

`PreferencesStore.patch` raising `ValueError` only matters if the route turns it into a 422
rather than a 500 — or worse, writes the key. The test also asserts `preferences.json` was
not created, so a rejected patch is proved to be a no-op on disk.

### 3 — the log outlived the retraction

`index.css` now matches what was measured; the owning log did not. Corrected by annotation
(struck + a dated correction block with the two measured regressions), consistent with how
`task-9`/`task-10`/`task-15`/`task-17` corrections were handled on this branch, rather than
by silently rewriting the sentence.

**`877ff90` breached this project's update-log rule** — it changed `index.css` with no log
entry at all. Recorded here and in the corrected log itself.

## Files touched

- `apps/web-client/src/App.tsx` — `handleDeleteAllSessions` returns `DeleteReport` and
  rethrows; `handleReindex` returns `ReindexReport` and rethrows; `handleConnectGDrive` /
  `handleDisconnectGDrive` rethrow. Status-pill writes unchanged.
- `apps/web-client/src/components/settings/SettingsPanel.tsx` — prop types for the four
  handlers, with the reasoning on the props themselves. **Shared seam** (every panel).
- `apps/web-client/src/components/settings/panels/DataPanel.tsx` — `clearError` /
  `clearReport` state, `role="alert"` + `role="status"` surfaces in the danger zone,
  scroll-into-view, measured-contrast note.
- `apps/web-client/src/components/settings/panels/KnowledgePanel.tsx` — `busy` /
  `actionError` / `notice` state, `run()` wrapper for all four actions, in-flight button
  labels and disabling, `summarize()` (including per-document reindex errors), the two
  surfaces, scroll-into-view.
- `services/assistant-core/tests/test_settings_locked.py` — `_patch(router)` helper +
  `test_patch_rejects_a_locked_key_with_422`.
- `logs/dark-mode-contrast-sweep_2026-07-28_log.md` — shared-seam note corrected in place.

No backend behaviour changed. `routes/settings.py` was mutated and restored bit-for-bit
during verification (`git diff` clean).

## Interfaces / contracts changed

Frontend prop contracts only — all four are internal to `App` → `SettingsPanel` → panel:

- `onDeleteAllSessions: () => Promise<void>` → `() => Promise<DeleteReport>`, **now rejects**
- `onReindex: (full, source?) => void` → `=> Promise<ReindexReport>`, **now rejects**
- `onConnectGDrive` / `onDisconnectGDrive`: `() => void` → `() => Promise<void>`, **now
  reject**

No HTTP contract, schema, or env var changed.

## Status

done

## Verification

- `python -m pytest` (system interpreter, repo root) → **307 passed** (306 before; +1 new).
- **Mutation test of the new assertion.** Deleted the `try/except ValueError → HTTPException(422)`
  in `routes/settings.py::patch_settings`:
  - `test_patch_rejects_a_locked_key_with_422` → **FAILED** (`ValueError: unknown or
    non-editable key: allow_shell_tools` propagated instead of a 422), other 3 in the file
    still passed — so the new test is the discriminating one, not a passenger.
  - Guard restored; `git diff` on the file is empty; 4 passed.
- `cd apps/web-client && npm run build` → PASS, no TS errors.
- **Browser, against an isolated database.** `DATABASE_URL=sqlite:///<scratch>/scratch.db`
  plus scratch `MEMORY_DIR` / `KNOWLEDGE_DIR`, `LLM_PROVIDER=mock`, `RAG_PROVIDER=vector`,
  Vite on 5173. `data/violet.db` verified byte-identical to a pre-work copy afterwards
  (still 30 sessions / 111 messages); the clear was never run against it.
  - **Baseline reproduced:** 0 `[role=alert]` in the dialog; `elementFromPoint` at the
    status pill returns the scrim element.
  - **Success, light:** "Cleared 3 sessions and 6 messages." rendered in-dialog,
    `role="status"`, geometrically inside the dialog rect, topmost at its own centre;
    confirm field cleared.
  - **Failure, light** (backend killed): "Nothing was deleted / Failed to fetch — your
    sessions are still there…" rendered in-dialog, `role="alert"` 0 → 1, topmost, and the
    typed `"delete"` preserved for retry. Status pill simultaneously read "Failed to fetch"
    and was confirmed still covered by the scrim.
  - **Both repeated in dark** (`documentElement.dataset.theme = "dark"`, the exact stamp
    `applyAppearance()` uses) with the ratios tabled above.
  - **Knowledge:** Reindex success → "Indexed 0, skipped 1, removed 0 (0 chunks)."
    in-panel; Reindex with the backend down → "Reindex failed: Failed to fetch" as
    `role="alert"`, in view, topmost, button label cycling Reindex → Reindexing… → Reindex.
- `data/preferences.json` restored from a copy of the real file; reads
  `{"ui_mode": "developer"}`.

## Next

Everything else from the review is triaged post-merge. The one thing worth carrying forward:
the "action reports only through the status pill" pattern is now fixed in `DataPanel` and
`KnowledgePanel`, but `App.tsx` still has several handlers on that shape
(`handleOpenSession`, `handleToolDecision`, chat `send`) — those are reached from outside the
settings dialog, so the pill is visible for them today. If any of them ever gains a control
inside Settings, it inherits the same defect.
