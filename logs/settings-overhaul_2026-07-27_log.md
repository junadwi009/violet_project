# Settings overhaul — design spec

- **Date:** 2026-07-27
- **Track:** cross-cutting (Track 1 Chat — web-client + assistant-core)
- **Branch:** main
- **Author:** Claude (brainstorming session)

## What
Wrote the approved design spec for restructuring the settings menu: the
500-line single-column `SettingsModal.tsx` becomes a sidebar-nav modal with one
panel per group, four new setting groups (Appearance, Model & routing, Voice,
Data & privacy) are added, and the existing behavioral defects are fixed in the
same pass. No code changed yet — spec only.

## Why
`SettingsModal.tsx` had accumulated ten unrelated concerns in one narrow
scrolling column and could not absorb another group. Several existing groups
were also broken: persona/provider selections did not survive a reload despite
`default_personality` / `default_provider` existing as editable keys, the
`overridden` / `defaults` payload was fetched and discarded, and the temperature
slider issued one HTTP request plus one file write per 0.1 step of drag.
Restructuring and fixing separately would have meant rewriting the same file
twice.

## Files touched
- `docs/superpowers/specs/2026-07-27-settings-overhaul-design.md` (new)
- `logs/settings-overhaul_2026-07-27_log.md` (new)

## Interfaces / contracts changed
None yet — spec only. Planned for implementation:
- `EDITABLE_KEYS` shape changes from `dict[str, Callable]` to
  `dict[str, PrefSpec]` (adds a `group` field; validation behavior unchanged).
- 14 new editable preference keys → 25 total (appearance ×4, voice ×5,
  model ×5).
- New routes: `POST /api/settings/reset`, `DELETE /api/sessions`,
  `DELETE /api/sessions/{session_id}`, `GET /api/export`.
- `GET /api/settings` response gains a read-only `locked` block (allowlisted
  safety flags, eight names).
- `SQLiteStore` gains `delete_session` / `delete_all_sessions` with explicit
  cascade (schema has no `ON DELETE CASCADE` and SQLite does not enforce FKs
  without `PRAGMA foreign_keys=ON`).
- No new env vars. Security boundary unchanged: API keys, base URLs, paths and
  `ALLOW_*` flags stay frozen in `.env` — the new panel displays them read-only
  and offers no path to change them.

## Status
done (spec) — implementation plan not yet written

## Verification
`grep -nE "TBD|TODO|FIXME"` over the spec → no placeholders. Spec self-review
pass caught and fixed four gaps: `accent` was declared an enum with no token
system behind it, `ui_density` / `font_scale` had no concrete definition, the
approved mockup's "Advanced" nav entry was unreconciled with the actual dev-only
groups, and `llm_provider` appearing in both `locked` and as the
`default_provider` fallback read as a contradiction. Not yet reviewed by user.

## Next
User reviews the spec, then `writing-plans` to produce the implementation plan.
Planned commit split: (1) extract existing panels with behavior unchanged,
(2) add new groups and keys — so any regression bisects to one of the two.
