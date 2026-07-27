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

3. **Task 7 fix pass** (`d771d70`) — review of the export bundle found the
   secrets check was name-based only: `test_export_excludes_locked_and_secrets`
   greps the serialized body for `api_key|base_url|token|secret|password`, which
   a leak that *relabels* the field (`{"endpoint": settings.llm_base_url}`)
   walks straight past. `d771d70` added
   `test_export_excludes_secret_values`, which gives every secret-bearing
   `Settings` field a distinctive canary value and asserts none of those
   **values** appear in the body under any key name, plus a pinned field count
   so a newly added secret can't silently join `Settings` uncovered. The same
   pass added `test_create_app_wires_the_export_router`: every other test in the
   file reaches the handler by walking `router.routes`, so
   `include_router(create_export_router(...))` could have been deleted from
   `main.py` with the file still green. Test-only change, no production code:
   243 → 245 passed.

4. **`VIOLET_API_TOKEN` gate on `GET /api/export`** (task 7b, this pass) — see
   the dedicated section below.

## Task 7b — gating the export endpoint

Not in the original plan; added by user decision on 2026-07-27 after a review
of task 7 verified live that `assistant-core` has **no authentication
anywhere**, and that the CORS middleware in `main.py` uses
`allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+"` with
`allow_credentials=True`. Any page served from any localhost port — another dev
server, a local Electron app, an npm postinstall that opens a listener — could
`fetch('/api/export')` and read the user's entire session, message and memory
corpus in one cross-origin GET. The CORS config predates this branch, but
`/api/export` is the first endpoint where a single GET returns everything. The
user chose to gate this one endpoint rather than tighten CORS globally (which
risks breaking local tooling); tightening CORS and authenticating other
endpoints are explicitly out of scope.

**Fail closed.** `violet_api_token` was added to `Settings`
(`VIOLET_API_TOKEN`, default `""`). When it is empty the endpoint is
**disabled** (503 naming the env var), not open — a data-egress endpoint that
is open by default is the thing this task exists to fix, so the user opts in by
setting the env var. With a token configured: no header, a non-`Bearer` scheme,
an empty or multi-word credential, or a wrong token → **401**; the correct
`Authorization: Bearer <token>` → **200** and the bundle exactly as before.
The token is compared with `hmac.compare_digest` on the utf-8 encoded values,
not `==`, so the check does not return early on the first differing byte and
leak the token's length and prefix through response timing. Neither the 401 nor
the 503 body echoes any part of the configured token — a rejection that quotes
what it expected is an oracle.

The gate lives in `_require_api_token(settings)` and is attached as a router
level `Depends`, so the handler body — the bundle assembly — is **unchanged**:
its contents and `Content-Disposition` header are byte-identical to what
`8878b46`/`d771d70` produced. `git diff` on `routes/export.py` touches only the
imports, the new dependency factory, and the `APIRouter(...)` line.

**Honest limitation — corrected 2026-07-27 (fix pass).** The web client is
legitimately cross-origin (Vite on 5173 → API on 8000), so when Task 15 wires
the Data panel it will have to carry the token in its bundle, and a local
attacker who can read that bundle can read the token. But that is not the
dominant gap. `GET /api/sessions`, `GET /api/sessions/{id}/messages`, and
`GET /api/memory` are all still ungated and cross-origin-readable (same CORS
policy, no dependency), and together they return essentially the same data as
the export bundle — session list, every message, every memory — just as N+1
requests instead of one. `DELETE /api/sessions` is likewise reachable as a
single unauthenticated cross-origin call and is destructive, which the export
gate does nothing to address. So the gate does **not** put the data "behind a
bar" — it raises attacker *cost* (a loop instead of one GET), not attacker
*capability*. Framing this as "raises the bar against a drive-by fetch" is
accurate only for the single export request; the previous wording ("raises the
bar ... nothing stronger") read as if that bar covered the underlying data,
which it does not. This — the three ungated read endpoints plus the ungated
destructive `DELETE /api/sessions` — is the dominant outstanding risk from
this task, ahead of the token-in-client-bundle issue. The remaining endpoints
are still unauthenticated.

`violet_api_token` is a secret: it is **not** in `EDITABLE_KEYS`
(`preferences/store.py`) and **not** in `LOCKED_KEYS` (`routes/settings.py`),
so it is never exposed through `GET /api/settings`, and it is covered by the
export canary loop below.

**Widened secrets canary.** `test_export_excludes_secret_values` selected
canary fields by `name.endswith("_api_key") or name.endswith("_base_url")` — 18
fields. Review demonstrated the hole: `gdrive_token_path` names a file holding a
live Google refresh token and sat outside that loop, caught only by accident
because its *default value* contains the literal word `token`, which the older
name-based regex in `test_export_excludes_locked_and_secrets` matches. Point
`GDRIVE_TOKEN_PATH` at a path without that word and an identical leak passed all
five tests — reproduced, see Verification. The selector is now a regex over
whole `_`-delimited segments —
`_(api_key|base_url|token|secrets?|password|credentials)(_|$)` — which covers
`gdrive_token_path`, `google_oauth_client_secrets`, and the new
`violet_api_token`; the pinned count moved 18 → **21**.

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
  two passes), `services/assistant-core/tests/test_export.py` (new, task 7;
  extended by `d771d70` and again by task 7b).
- Task 7b: `services/assistant-core/src/violet_assistant/config.py` —
  `Settings.violet_api_token` + `VIOLET_API_TOKEN` in `load_settings`.
- Task 7b: `services/assistant-core/src/violet_assistant/routes/export.py` —
  `_require_api_token(settings)`, attached as a router-level `Depends`. Bundle
  assembly untouched.
- Task 7b: `.env.example` — the `VIOLET_API_TOKEN` line is no longer a
  "placeholder for later phases"; the comment now states what it gates.
- Task 7b: `services/assistant-core/tests/test_export.py` — auth tests via
  `TestClient(create_app(...))`, widened canary selector.

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
- Task 7b: `GET /api/export` now requires `Authorization: Bearer
  <VIOLET_API_TOKEN>`. 503 when the env var is unset (endpoint disabled), 401
  on a missing/malformed/wrong token, 200 with the unchanged bundle otherwise.
  Any existing caller must be updated — the Data panel (Task 15) must surface
  *why* export is unavailable rather than shipping a dead download link.
- Task 7b: new env var `VIOLET_API_TOKEN` (already present in `.env.example`,
  now live rather than a placeholder). `Settings.violet_api_token: str = ""`.
  No schema/migration change. Tasks 6–7 added no env vars.

## Status
done — Phase B (tasks 6–7, plus the out-of-plan task 7b) complete. Phase B is
the last phase of the backend track; Phase C/D (frontend) starts next.

## Verification
- Task 6, first pass (`5915403`): full suite → 224 baseline + 13 new
  delete-session tests = 237 passed. Task 6, hardening pass (`6d01ae1`):
  240 passed (237 − 1 removed test + 4 added).
- Task 7 red: `python -m pytest services/assistant-core/tests/test_export.py -q`
  → `ModuleNotFoundError: No module named 'violet_assistant.routes.export'`
  (collection error), before `routes/export.py` existed.
- Task 7 green: same command → **3 passed**.
- Full suite after task 7: `python -m pytest` (repo root) → **243 passed**,
  8 warnings, ~22–29s. (240 at the start of Task 7 + 3 new in
  `test_export.py`. Phase B as a whole — tasks 6–7 — started at 224.)
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
- Task 7 fix pass (`d771d70`): full suite → **245 passed** (243 + 2 new tests,
  no production change).
- Task 7b red: `python -m pytest services/assistant-core/tests/test_export.py -q`
  → **17 failed, 3 passed**, for the expected reasons —
  `TypeError: Settings.__init__() got an unexpected keyword argument
  'violet_api_token'` (every auth test), `AssertionError: assert 20 == 21` (the
  widened canary count), and `assert 'hmac.compare_digest(' in <source>` (the
  constant-time pin).
- Task 7b green: same command → **20 passed**. Full suite `python -m pytest`
  (repo root) → **260 passed**, 73 warnings, ~20–33s (245 + 15 new).
- Break-it verification for task 7b (each mutation applied, full suite run,
  then reverted; `grep -r "MUTATION PROBE"` confirmed no residue and the suite
  re-run green at 260):
  1. **503-when-unset branch removed** (`if not expected: return` — fail open
     instead of raising). Result: **1 failed** —
     `test_export_is_disabled_when_no_token_is_configured`, `assert 200 == 503`.
  2. **`hmac.compare_digest` → `presented != expected`.** Result: **1 failed**,
     but only `test_token_comparison_is_constant_time`, which asserts on the
     module *source text*. Re-running with that test deselected: **259 passed,
     1 deselected** — i.e. **no behavioral test distinguishes constant-time
     from plain comparison**, and none can: a timing side channel is not
     observable from a test process with any reliability. Recorded here rather
     than papered over. The static pin catches a refactor that swaps the
     comparison back out; it proves nothing about actual timing.
  3. **401 branch removed** (dependency returns after the 503 check, accepting
     any or no token). Result: **12 failed** — all 11
     `test_export_rejects_missing_or_malformed_authorization` /
     `test_export_rejects_a_wrong_bearer_token` cases, plus the constant-time
     pin (the comparison went with the branch).
  4. **Widened canary.** Added `"storage_hint": settings.gdrive_token_path` to
     the bundle — an innocuous key name — and ran with
     `GDRIVE_TOKEN_PATH=C:/tmp/gd_cred.json`, a path containing neither "token"
     nor "secret". Against the pre-fix tests at `d771d70`: **5 passed** — the
     leak is invisible, exactly the hole review demonstrated. Against the
     widened tests: **2 failed** — `test_export_excludes_secret_values`
     (`secret value for 'gdrive_token_path' leaked into export bundle`) and
     `test_export_serves_the_unchanged_bundle_with_the_correct_token`, whose
     exact-key-set assertion catches the extra key independently.

## Next
- Phase C/D (frontend, Tasks 8–18): the Data settings panel (Task 15) adds
  the export button above the "clear all sessions" control from Task 6, and
  wires both to these two endpoint groups.
- Task 15 must send `Authorization: Bearer <token>` from the web client and
  handle 503 (export disabled — tell the user to set `VIOLET_API_TOKEN`) and
  401 distinctly. Threading the token through the client is deliberately not
  part of task 7b.
- The token in the client bundle is readable by anything local that can read
  that bundle (see the honest limitation above). If the threat model ever grows
  past "drive-by fetch from another localhost page", the real fix is
  tightening CORS and authenticating the whole API, not a second token.
- No pagination or size cap on `GET /api/export` — for a local-first
  single-user SQLite deployment this is fine at current scale; would need
  revisiting if session/message volume grows large enough to make the
  synchronous JSON serialization slow.
