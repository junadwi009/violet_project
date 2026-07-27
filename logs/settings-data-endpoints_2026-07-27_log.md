# Settings overhaul — Phase B (session delete + export, tasks 6–7)

- **Date:** 2026-07-27
- **Track:** cross-cutting (Track 1 Chat — assistant-core data endpoints)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code

## What
Phase B of the settings-overhaul plan: two backend endpoints the new Data
settings panel (Phase C/D, Task 15) will call — a destructive one and a
backup one, landed in that order so the backup path exists before anyone
reaches for the destructive one.

1. **Session delete with explicit cascade** (`5915403`, hardened by
   `6d01ae1`) — `SQLiteStore.delete_session(session_id)` and
   `.delete_all_sessions()`, plus `DELETE /api/sessions/{id}` (404 on unknown
   id via `KeyError`) and `DELETE /api/sessions` on
   `routes/sessions.py`. The schema has no `ON DELETE CASCADE` and
   `SQLiteStore._connect` never issues `PRAGMA foreign_keys=ON`, so SQLite
   would otherwise leave orphaned rows — every child row is deleted by hand
   inside one transaction: `memory_candidates` scoped to the session's
   `messages` (matched via `source_message_id IN (SELECT id FROM messages
   WHERE session_id = ?)`, deliberately unfiltered by `status` so pending,
   approved, and rejected candidates are all swept), then `agent_runs`, then
   `messages`, then the `sessions` row itself. `memories` and
   `tool_audit_logs` are never touched by either method: an approved memory
   is meant to outlive the conversation that produced it, and an audit trail
   you can erase by clearing a chat isn't an audit trail.

   The first pass (`5915403`) landed the feature with a test file
   (`test_sessions_delete.py`) that covered the happy path and the
   pending-candidate case but did not pin two things: that the cascade is
   actually atomic (a failure on the final `DELETE FROM sessions` must not
   leave messages/candidates/agent_runs half-deleted), and that
   approved/rejected candidates — not just pending ones — get swept. Review
   caught both gaps by mutation: an autocommit refactor (each `DELETE`
   committed independently instead of inside one `with self._connect()`
   transaction) still passed the full suite, and so did narrowing the
   candidate cleanup query to `AND status = 'pending'`. `6d01ae1` closed
   both gaps — rollback tests that monkeypatch the connection so the final
   `sessions` `DELETE` raises, then read back through a *fresh* connection
   to confirm every child row survived, for both `delete_session` and
   `delete_all_sessions`; and coverage that seeds an approved and a rejected
   candidate and asserts both are gone. It also dropped
   `test_delete_unknown_session_leaves_data_untouched`, which could not
   distinguish "rolled back" from "the `WHERE session_id = ?` just never
   matched anything" and so proved nothing the new rollback tests didn't
   already cover for real. No production code changed in `6d01ae1` — test
   file only, 240 passed (237 baseline − 1 removed + 4 added).

2. **`GET /api/export`** (this task) — `routes/export.py`:
   `create_export_router(store, memory_store, preferences, settings)`
   returning a single-endpoint router. The handler assembles a JSON bundle —
   `exported_at`, `schema_version: 1`, `sessions` (from
   `store.list_sessions()`), `messages` (from
   `store.messages_for_session(session_id)` per session, with `session_id`
   re-attached to each row since that method's return shape omits it),
   `memories` (from `memory_store.list()`, already JSON-shaped), and
   `preferences` (`{"values": preferences.effective(settings), "overridden":
   preferences.overridden()}`) — and returns it as a `Response` with
   `Content-Disposition: attachment; filename="violet-export-{UTC
   timestamp}.json"` so the browser downloads it instead of rendering it
   inline. It deliberately does **not** include the `locked` safety block
   that `GET /api/settings` exposes (see Phase A log, task 5): this is a
   user-data backup, not a config dump, and shouldn't carry a snapshot of
   the deployment's safety posture into a file that gets emailed around.
   Wired into `main.py` next to `create_sessions_router`, passing the same
   `store`, `memory_store`, `preferences`, and `active_settings` instances
   already built in `create_app()`.

## Why
Task 6 makes "clear all sessions" possible from the UI; Task 7 exists so a
backup path is available *before* that control is ever exposed — the Data
panel (Task 15) places the export button above the destructive controls.
Excluding `locked` from the export isn't an oversight-avoidance measure, it's
the point: an export is something a user might attach to an email or drop in
a shared drive, and the safety-flag block (`allow_shell_tools`,
`tool_confirm_threshold`, etc.) has no reason to travel with it.

## Files touched
- `services/assistant-core/src/violet_assistant/persistence/sqlite_store.py`
  — `delete_session`, `delete_all_sessions`.
- `services/assistant-core/src/violet_assistant/routes/sessions.py` —
  `DELETE /api/sessions/{session_id}`, `DELETE /api/sessions`.
- `services/assistant-core/src/violet_assistant/routes/export.py` (new) —
  `create_export_router`, `GET /api/export`.
- `services/assistant-core/src/violet_assistant/main.py` — import +
  `app.include_router(create_export_router(store, memory_store, preferences,
  active_settings))`, registered next to the sessions router.
- Tests: `services/assistant-core/tests/test_sessions_delete.py` (task 6,
  two passes), `services/assistant-core/tests/test_export.py` (new, task 7).

## Interfaces / contracts changed
- `SQLiteStore.delete_session(session_id: str) -> dict[str, int]` — raises
  `KeyError` if the session doesn't exist; returns
  `{"deleted_sessions", "deleted_messages", "deleted_candidates",
  "deleted_agent_runs"}`. Whole operation runs inside one transaction.
- `SQLiteStore.delete_all_sessions() -> dict[str, int]` — same shape,
  unconditional, also one transaction.
- `DELETE /api/sessions/{session_id}` — 404 with `{"detail": "Session not
  found"}` on unknown id; 200 with the counts dict otherwise.
- `DELETE /api/sessions` — always 200 with the counts dict (0s if there was
  nothing to delete).
- `create_export_router(store, memory_store, preferences, settings) ->
  APIRouter` serving `GET /api/export`, returning
  `application/json` with `Content-Disposition: attachment`. Bundle shape:
  `{exported_at, schema_version, sessions, messages, memories,
  preferences: {values, overridden}}`. No `locked` key anywhere in the
  bundle, by construction (there is no code path that reads
  `settings.allow_shell_tools` or any other `LOCKED_KEYS` field into it).
- No new env vars. No schema/migration change.

## Status
done — Phase B (tasks 6–7) complete. Phase B is the last phase of the
backend track; Phase C/D (frontend) starts next.

## Verification
- Task 6, first pass (`5915403`): full suite → 237 baseline + delete-session
  coverage. Task 6, hardening pass (`6d01ae1`): 240 passed (237 baseline − 1
  removed test + 4 added).
- Task 7 red: `python -m pytest services/assistant-core/tests/test_export.py -q`
  → `ModuleNotFoundError: No module named 'violet_assistant.routes.export'`
  (collection error), before `routes/export.py` existed.
- Task 7 green: same command → **3 passed**.
- Full suite after task 7: `python -m pytest` (repo root) → **243 passed**,
  8 warnings, ~22–29s. (240 at Phase B start + 3 new in `test_export.py`.)
- Break-it verification performed before committing (each mutation applied
  to `routes/export.py`, confirmed to fail the export tests, then reverted
  and the full suite re-run green at 243):
  1. Added `"locked": {"probe": "mutation-test"}` to the bundle. Result:
     `test_export_excludes_locked_and_secrets` **failed** —
     `AssertionError: assert 'locked' not in {...}`.
  2. Changed the messages comprehension from `{**message, "session_id":
     session["id"]}` to `{**message}`, dropping the re-attached
     `session_id`. Result: `test_export_contains_user_data` **failed** —
     `KeyError: 'session_id'`.
  3. Removed the `headers={"Content-Disposition": ...}` argument from the
     `Response` construction. Result: `test_export_is_an_attachment`
     **failed** — `KeyError: 'content-disposition'` reading
     `response.headers["content-disposition"]`.
  4. Added `"debug_settings": {"llm_api_key": getattr(settings,
     "llm_api_key", "x")}` to the bundle, simulating a stray secret-shaped
     field making it into the export. Result:
     `test_export_excludes_locked_and_secrets` **failed** — the compiled
     `api_key|base_url|token|secret|password` regex matched
     `'api_key'` in the serialized body.
  - `git diff --stat` on `routes/export.py` confirmed clean (no residual
    mutation) before the final commit.

## Next
- Phase C/D (frontend, Tasks 8–18): the Data settings panel (Task 15) adds
  the export button above the "clear all sessions" control from Task 6, and
  wires both to these two endpoint groups.
- No pagination or size cap on `GET /api/export` — for a local-first
  single-user SQLite deployment this is fine at current scale; would need
  revisiting if session/message volume grows large enough to make the
  synchronous JSON serialization slow.
