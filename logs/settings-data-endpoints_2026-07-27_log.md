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

4. **`VIOLET_API_TOKEN` gate on `GET /api/export`** (task 7b) — see the
   dedicated section below.

5. **Tightened CORS** (task 7c, this pass) — removed the `allow_origin_regex`
   wildcard and `allow_credentials` from the `CORSMiddleware` config in
   `main.py`. See the dedicated section below.

6. **Exposed `Content-Disposition` cross-origin** (task 7d, this pass) — added
   `expose_headers=["Content-Disposition"]` to the same `CORSMiddleware` call.
   See the dedicated section below.

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

**Superseded in part by task 7c (2026-07-27).** The paragraph above remains an
accurate description of the *authentication* posture — the other endpoints are
still unauthenticated and that has not changed. What changed is who can reach
them. After task 7c a cross-origin attacker can no longer read any of them from
an arbitrary local page, so for that attacker the gate is no longer merely a
cost increase; the CORS allowlist is doing the real work, on every route rather
than on `/api/export` alone. The original framing stays true, unchanged, for
anything running with **local filesystem or local process access** — a script on
the machine, anything that can read the client bundle, or any client that is not
a browser (`curl`, a Python script) and is therefore not bound by CORS at all.
CORS is a browser-enforced control, not an authorization control. See the task
7c section for exactly what it does and does not buy.

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
`_(api_key|base_url|token|secrets?|password|credentials|database_url)(_|$)` —
which covers `gdrive_token_path`, `google_oauth_client_secrets`, the new
`violet_api_token`, and `database_url`; the pinned count moved 18 → **22**.

`database_url` joined the loop in the fix pass (`6bb431c`). Review demonstrated
a leak of that field that was previously **fully invisible**: unlike
`gdrive_token_path` — which the older name-based body grep caught by accident,
because its default *value* contains the word "token" — `database_url`'s value
matched none of `api_key|base_url|token|secret|password`, so a bundle carrying
it passed every test. It is listed by name rather than via a generic `url`
segment, because a generic segment would also sweep in `public_client_url`, a
non-secret browser URL. This repo is SQLite-only today so the current value is
harmless, but the field *shape* — a connection string that can embed
`user:pass@host` — is exactly what the canary loop exists to catch, and the
selector should not depend on the deployment staying SQLite.

## Task 7c — tightening CORS

Not in the original plan; added by user decision on 2026-07-27 after review of
task 7b demonstrated that the token gate raises attacker *cost*, not attacker
*capability* (see the corrected honest-limitation paragraph above). The user
chose to tighten CORS because it protects **every** route rather than one.

**What the wildcard exposed.** `main.py` already had an explicit
`client_origins` allowlist — `public_client_url` plus ports 3000 and 5173 on
both `localhost` and `127.0.0.1`. A second argument,
`allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+"`, made that allowlist
decorative: it admitted **every** localhost port, and `allow_credentials=True`
came along with it. Any page served from any local port — a second dev server, a
local Electron app, an npm postinstall that opens a listener — could read the
response of any endpoint. Concretely, `GET /api/sessions`,
`GET /api/sessions/{id}/messages` and `GET /api/memory` are all unauthenticated
and together reproduce essentially the whole export bundle that task 7b had just
put behind a token; and `DELETE /api/sessions`, which wipes every session and
message, was reachable as a single destructive cross-origin call.

**The change** is small and entirely in the `add_middleware` call:

- `allow_origin_regex` **deleted**. `client_origins` is now the single source of
  allowed origins. A comment in `main.py` records why and says explicitly: if a
  legitimate origin needs access, add it to `client_origins` (or set
  `PUBLIC_CLIENT_URL`) — do not reintroduce a regex.
- `allow_credentials` set to **False** (was `True`). Nothing here authenticates
  with cookies; the only credential is the task 7b `Authorization: Bearer`
  header, which this flag does not affect. `True` alongside `allow_headers=["*"]`
  is additionally a spec violation that browsers handle inconsistently. Kept as
  an explicit `False` rather than removed: Starlette's default is already
  `False`, so the emitted headers are identical either way, but stating it keeps
  the decision visible and independent of a framework default.
- `allow_headers=["*"]` **unchanged**, and verified to still permit
  `Authorization` — with `"*"` Starlette echoes the requested headers back on
  the preflight, and it does so independently of `allow_credentials`. So the
  `/api/export` gate is unaffected. No explicit `Authorization` entry was
  needed.
- The task 7b token gate and the export bundle itself are **untouched**.

**Origins the client actually uses.** `apps/web-client/vite.config.ts` sets port
5173 and the `dev` script passes `--host 127.0.0.1`, so the dev origin is
`http://127.0.0.1:5173` — allowlisted. `apps/web-client/nginx.conf` reverse
proxies `/api/` to `assistant-core:8000`, so the container case is same-origin
and never consults CORS at all. **Correction (fix pass, this pass):** the
original audit was wrong — `package.json`'s `preview` script
(`vite preview --host 127.0.0.1`) does not honor `server.port` from
`vite.config.ts` and serves on `4173` by default, a legitimate, repo-shipped
way of serving the client that the original `client_origins` set did not
cover. `http://localhost:4173` and `http://127.0.0.1:4173` have now been added
to `client_origins`.

**What this does and does not buy.** CORS is enforced by the *browser*, not the
server. It stops a hostile web page from reading these responses, which is the
threat the review actually demonstrated. It does nothing against a non-browser
client — `curl`, a Python script, anything with local process access — because
those never send an `Origin` header or honour the response. The endpoints
besides `/api/export` remain unauthenticated; this narrows who can reach them,
it does not authorize them. Authenticating the rest of the API is still the real
fix and is still out of scope.

### Browser verification (required by the task, performed)

Backend on `127.0.0.1:8000` (via `.venv`), Vite dev client on
`http://127.0.0.1:5173`, loaded in a real Chrome instance.

- **Client works.** Every API call the client makes on load is cross-origin
  (5173 → 8000) and every one is *preflighted*, because the client sends
  `Content-Type: application/json` even on GETs. Observed: `OPTIONS` **200** and
  `GET` **200** for `/api/personalities`, `/api/settings`, `/api/sessions`,
  `/api/providers`, `/api/memory`, `/api/memory/candidates`, `/api/memory/info`,
  `/api/agents`, `/api/skills`, `/api/knowledge`. **Zero CORS errors in the
  console** (only Vite's connect messages and the React DevTools notice). The UI
  populated with live data: personality "Violet", engine badge "Local" from
  `/api/providers`, and the Memory panel showing "2 pending · 2 approved" with
  the real backend path and real candidate contents. An in-page `fetch` from the
  client's own origin returned readable bodies for `/api/personalities`,
  `/api/settings`, `/api/sessions` and `/api/providers` (200 each).
- **Attacker origin is blocked.** A static probe page served from
  `http://localhost:31337` — a port the old regex allowed — got
  `TypeError: Failed to fetch` for `/api/sessions`, for `/api/memory`, and for a
  preflighted request. Nothing readable.
- **Browser-level mutation.** Reinstating `allow_origin_regex` +
  `allow_credentials=True` and restarting the backend, that *same* probe page
  read **3198 bytes** of real session data and **566 bytes** of real memories,
  and its preflight was approved (`200`). Restoring the fix and restarting
  returned it to blocked. This is the vulnerability and its closure demonstrated
  end to end in a real browser, not inferred from a test suite.
- The probe deliberately used a custom-header GET as the preflight stand-in
  rather than firing a real `DELETE /api/sessions`: same origin check, same
  middleware, same verdict, but no risk to the developer's live database if the
  hardening had been wrong.

### Vite `strictPort` trap — fixed (fix pass, this pass)

`vite.config.ts` set `strictPort: false`, so if 5173 was already occupied Vite
would silently start on 5174 — an origin `client_origins` does not allowlist.
The fetch itself throws an opaque `TypeError: Failed to fetch` in code (the
`TypeError` carries no mention of CORS), but the browser console is not silent
about it: Chrome logs an explicit `Access to fetch at '...' from origin
'http://127.0.0.1:5174' has been blocked by CORS policy: No
'Access-Control-Allow-Origin' header is present on the requested resource.`
alongside the `TypeError`, so a developer looking at DevTools does get a
direct hint. This was not hit during the original verification (5173 was
free). **Fixed here:** `strictPort: true`, so a busy port now aborts the dev
server at startup with a clear error instead of silently relocating it to a
rejected origin — a deliberate DX tradeoff (a port clash now fails loudly
rather than producing a confusing runtime CORS failure). Adding 5174 to
`client_origins` would only have moved the problem to 5175, so that was not
done.

## Task 7d — exposing `Content-Disposition` cross-origin

The new `downloadExport()` client function in `apps/web-client/src/lib/api.ts`
(landed at `7f01d4d`, this branch's HEAD before this pass) reads
`Content-Disposition` off the `/api/export` response to name the downloaded
file `violet-export-YYYYMMDD-HHMMSS.json`. Task 7c's `CORSMiddleware` call had
no `expose_headers`, which defaults to `[]`, and `Content-Disposition` is not
in the small header safelist CORS exposes to cross-origin `fetch()` by
default. In the standard dev setup (client on 5173, API on 8000, same
allowed-origin case task 7c hardened) `response.headers.get('content-disposition')`
therefore read back `null` and the client silently fell back to a generic
`violet-export.json`. One line: `expose_headers=["Content-Disposition"]`
added to the existing `add_middleware(CORSMiddleware, ...)` call, plus a
comment above it explaining why. Nothing else in the CORS config changed —
`client_origins`, `allow_credentials=False`, and the deliberate absence of
`allow_origin_regex` (task 7c) are untouched.

Pinned with `test_export_content_disposition_is_exposed_cross_origin` in
`test_cors.py`: builds a real `create_app()`, hits the actually-gated
`GET /api/export` with an allowed `Origin` and a valid bearer token (reusing
the `test_export._app_settings` token pattern via `dataclasses.replace`), and
asserts both that the response carries `content-disposition` and that
`access-control-expose-headers` contains it — so the test fails the way the
real client bug would (header present on the response, but not readable
cross-origin) rather than asserting on the middleware call's arguments
directly.

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
  "placeholder for later phases". The fix pass (`6bb431c`) changed the **value
  to empty**, which is the substantive part: the template previously shipped
  `VIOLET_API_TOKEN=change_me_local_dev`, and a documented default copied
  verbatim into a real `.env` is a publicly-known token that defeats the
  fail-closed gate entirely. The comment was rewritten to state what the var
  gates *and* to say why the template value must stay empty.
- Task 7b: `services/assistant-core/tests/test_export.py` — auth tests via
  `TestClient(create_app(...))`, widened canary selector.
- Task 7b fix pass (`6bb431c`): `pyproject.toml` — added `pytest-asyncio` and
  `httpx` to the `dev` extra. Both were already required by the test suite
  (`@pytest.mark.asyncio` throughout `test_export.py`; `httpx` is what
  `fastapi.testclient.TestClient` is built on) but neither was declared, so the
  documented setup — `pip install -e ".[dev]" && python -m pytest`, given in
  both `CLAUDE.md` and `README.md` — **failed at collection** from a clean
  environment. Review verified this by building a fresh venv. It now works.
- Task 7c: `services/assistant-core/src/violet_assistant/main.py` — removed
  `allow_origin_regex`, set `allow_credentials=False`, added the explanatory
  comment. No other production file changed.
- Task 7c: `services/assistant-core/tests/test_cors.py` (new) — 39 tests
  pinning the allowlist, the disallowed origins, the refused preflights, the
  absent credentials header, and the absence of the regex argument.
- Task 7c fix pass (this pass, review of `7536320`): `main.py` — added
  `http://localhost:4173` / `http://127.0.0.1:4173` (vite preview's default
  port) to `client_origins`, with a comment. `test_cors.py` — moved
  `http://localhost:4173` from `DISALLOWED_ORIGINS` to the allowed-origin
  parametrization (and added `http://127.0.0.1:4173` alongside it), replacing
  it in `DISALLOWED_ORIGINS` with `http://localhost:4174` (an unallowlisted
  neighbor port) so the disallowed-origin coverage is not weakened.
  `apps/web-client/vite.config.ts` — `strictPort: false` → `true`.
- Task 7d: `services/assistant-core/src/violet_assistant/main.py` — added
  `expose_headers=["Content-Disposition"]` to the `CORSMiddleware` call, plus
  an explanatory comment. No other production file changed.
- Task 7d: `services/assistant-core/tests/test_cors.py` —
  `test_export_content_disposition_is_exposed_cross_origin` (new), plus
  `EXPORT_TOKEN` constant.

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
- Task 7c: **browser-visible behaviour change, no Python API change.** Requests
  from origins outside `client_origins` no longer receive
  `Access-Control-Allow-Origin`; preflights from those origins get **400
  "Disallowed CORS origin"**. `Access-Control-Allow-Credentials` is no longer
  emitted at all. Any local tool that relied on reaching this API from a browser
  page on an arbitrary localhost port will now fail — that is the intent. Add
  the origin to `client_origins`, or set `PUBLIC_CLIENT_URL`. Non-browser
  clients (`curl`, scripts, the container's same-origin nginx proxy) are
  unaffected. Task 7c added no env vars.
- Task 7d: `GET /api/export` response now also carries
  `Access-Control-Expose-Headers: Content-Disposition` on any CORS response
  (simple or preflight-approved), so a cross-origin `fetch()` from an
  allowed origin can read `response.headers.get('content-disposition')`.
  Purely additive; no other header or status code changed. No env vars added.

## Operational — ACTION REQUIRED: rotate `VIOLET_API_TOKEN`
This machine's git-ignored `.env` is gated by `change_me_local_dev` — the value
that shipped in `.env.example` and is therefore **in git history**. A token that
is public knowledge is not a gate: anyone reading this repo can authenticate to
`GET /api/export` and pull every session, message and memory. The fix pass
(`6bb431c`) emptied the value in `.env.example` so new setups can't inherit it,
but that does nothing for an `.env` already carrying it.

**Rotate it.** Generate a fresh value and put it only in `.env`:

```
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Recorded here rather than only in `.superpowers/sdd/task-7b-report.md`: that
path is a gitignored review-cycle artifact, not the project's durable record,
so the single operational item a human must act on was invisible to anyone
reading the logs. This item is **not** resolved by task 7c — CORS is
browser-enforced, and a known token plus `curl` bypasses it entirely.

## Status
done — Phase B (tasks 6–7, plus the out-of-plan tasks 7b, 7c and 7d) complete.
Phase B is the last phase of the backend track; Phase C/D (frontend) starts
next. One operational item is **open and needs a human**: rotate
`VIOLET_API_TOKEN` (see Operational above).

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
- **Task 7b fix pass (`6bb431c`)** — previously unrecorded; backfilled here
  during task 7c because `CLAUDE.md` marks the update log **WAJIB** and this
  commit had no Verification entry at all. Findings below are the *reviewer's*,
  recorded from the task 7b review cycle rather than re-run in this pass:
  - Full suite `python -m pytest` (repo root) → **260 passed** — the same count
    as task 7b green. The pass added no tests; it widened the canary selector
    (pinned count 21 → **22**, `database_url` added) and corrected the log.
  - Clean-environment check: the reviewer built a **fresh venv** and confirmed
    `pip install -e ".[dev]" && python -m pytest` — the setup documented in both
    `CLAUDE.md` and `README.md` — **failed at collection** before this commit
    and **works after it**. `pytest-asyncio` and `httpx` were used by the suite
    but undeclared in the `dev` extra.
  - `database_url` leak: the reviewer demonstrated a leak of that field that was
    **fully invisible** to every pre-fix test, because unlike `gdrive_token_path`
    its value contains none of `api_key|base_url|token|secret|password` and so
    tripped neither the name-based body grep nor the old canary selector. It is
    now inside the canary loop.
  - `.env.example`: `VIOLET_API_TOKEN` value emptied (was
    `change_me_local_dev`). See the rotation item under "Operational" above —
    this is the one thing a human still has to do.
- **Task 7c** (this pass; system interpreter, see the note below):
  - Red: `python -m pytest services/assistant-core/tests/test_cors.py -q` →
    **20 failed, 19 passed**, for the expected reasons — disallowed localhost
    origins were echoed in `access-control-allow-origin`, disallowed preflights
    returned 200, `access-control-allow-credentials: true` was present, and the
    `allow_origin_regex` source pin failed.
  - Green: same command → **39 passed**.
  - Full suite `python -m pytest` (repo root) → **299 passed**, 225 warnings,
    ~88s. 260 baseline + 39 new; no pre-existing test changed or broke.
  - Break-it verification (each mutation applied to `main.py`, CORS tests run,
    then reverted; `main.py` restored from a byte-identical backup and
    `grep -c "allow_origin_regex="` → **0** before committing):
    1. **`allow_origin_regex` reinstated** — the defect itself. Result: **19
       failed**. All 12 `test_disallowed_origin_is_not_echoed` cases for the
       three localhost origins across `/health`, `/api/sessions`, `/api/memory`
       and `/api/export`; all 3 `test_preflight_for_destructive_delete_is_refused`
       and all 3 `test_preflight_for_export_is_refused` localhost cases; plus
       `test_main_source_passes_no_origin_regex`. The `evil.example` cases
       correctly stayed green — that origin never matched the regex.
    2. **`allow_credentials=True`.** Result: **1 failed** —
       `test_credentials_are_not_allowed`.
    3. **`active_settings.public_client_url` dropped from `client_origins`.**
       Result: **1 failed** — `test_public_client_url_is_allowed`, which pins a
       value outside the hardcoded 3000/5173 literals precisely so this mutation
       cannot hide behind them.
    4. **`allow_origins=["*"]`.** Result: **37 failed, 2 passed**.
  - Live server check (`curl` against a running uvicorn, not TestClient):
    `Origin: http://localhost:5173` → `access-control-allow-origin:
    http://localhost:5173`; `Origin: http://localhost:31337` → **no** ACAO
    header; preflight `OPTIONS` + `Access-Control-Request-Method: DELETE` from
    `http://localhost:31337` → **400**, no ACAO. No
    `access-control-allow-credentials` on any of them.
  - Browser verification: see the dedicated subsection in the task 7c section
    above, including the browser-level mutation in which the attacker page read
    3198 bytes of real sessions and 566 bytes of real memories with the regex
    restored, and nothing with it removed.
- **Task 7c fix pass** (this pass, addressing review findings on `7536320`):
  - `python -m pytest services/assistant-core/tests/test_cors.py -q` after
    adding the two 4173 origins and moving the test case → **41 passed** (39
    baseline + 2 new parametrizations of `test_allowed_origin_is_echoed` for
    `http://localhost:4173` and `http://127.0.0.1:4173`).
  - Mutation: removed the two new 4173 entries from `client_origins` in
    `main.py` again and re-ran the same command → **2 failed, 39 passed**,
    both failures exactly
    `test_allowed_origin_is_echoed[http://localhost:4173]` and
    `test_allowed_origin_is_echoed[http://127.0.0.1:4173]`. Confirms the test
    actually pins the fix rather than passing regardless. `main.py` restored
    to the fix (`diff` against a pre-mutation copy showed no difference).
  - Full suite `python -m pytest` (repo root) → **301 passed** (299 baseline +
    2 new).
- **Task 7d** (this pass; system interpreter):
  - `python -m pytest services/assistant-core/tests/test_cors.py -q` →
    **42 passed** (41 baseline + 1 new).
  - Mutation: removed `expose_headers=["Content-Disposition"]` from the
    `CORSMiddleware` call in `main.py` and re-ran the same command →
    **1 failed, 41 passed** — exactly
    `test_export_content_disposition_is_exposed_cross_origin`,
    `AssertionError: assert 'Content-Disposition' in ''`. Confirms the test
    fails without the fix rather than passing regardless. `main.py` restored
    (`git diff` against the pre-mutation state showed no difference).
  - Full suite `python -m pytest` (repo root) → **302 passed** (301 baseline +
    1 new), ~93s, no flaky `test_agent_loop.py` error this run.

**Interpreter note.** The repo `.venv` lacks `httpx` and `pytest-asyncio`, so
the suite cannot be collected there; `.venv` was **not** modified. All pytest
runs above used the **system interpreter** (Anaconda Python 3.13), which has
both. The uvicorn backend for the browser check was run from `.venv`, which does
have `violet_assistant` installed editable and does not need `httpx`.

## Next
- Phase C/D (frontend, Tasks 8–18): the Data settings panel (Task 15) adds
  the export button above the "clear all sessions" control from Task 6, and
  wires both to these two endpoint groups.
- Task 15 must send `Authorization: Bearer <token>` from the web client and
  handle 503 (export disabled — tell the user to set `VIOLET_API_TOKEN`) and
  401 distinctly. Threading the token through the client is deliberately not
  part of task 7b.
- The token in the client bundle is readable by anything local that can read
  that bundle (see the honest limitation above). Half of the follow-up named
  here originally — tightening CORS — is now done (task 7c). **Authenticating
  the whole API is not**, and remains the real fix: CORS constrains browsers
  only, so `curl` and any local script still reach every endpoint except
  `/api/export` unauthenticated, including `DELETE /api/sessions`.
- **Rotate `VIOLET_API_TOKEN`** — see the Operational section above. Unresolved,
  needs a human.
- `apps/web-client/vite.config.ts` now sets `strictPort: true` (fix pass). A
  busy 5173 aborts the dev server instead of silently moving it to 5174, an
  origin the tightened allowlist rejects. Resolved.
- No pagination or size cap on `GET /api/export` — for a local-first
  single-user SQLite deployment this is fine at current scale; would need
  revisiting if session/message volume grows large enough to make the
  synchronous JSON serialization slow.
