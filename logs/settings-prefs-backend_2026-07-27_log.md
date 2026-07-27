# Settings overhaul — Phase A (preferences backend, tasks 1–5)

- **Date:** 2026-07-27
- **Track:** cross-cutting (Track 1 Chat — assistant-core preferences/settings)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code

## What
Phase A of the settings-overhaul plan: rebuilt the preferences backend that the
new settings UI (Phase B onward) will sit on top of. Five tasks, each landed with
its own TDD red/green cycle and commit:

1. **`PrefSpec` group metadata** (`d7d69f9`) — `EDITABLE_KEYS` changed shape from
   `dict[str, Callable]` to `dict[str, PrefSpec]`, where `PrefSpec` carries the
   existing validator plus a new `group` field (`general` / `model` / `behavior`).
   Added `keys_in_group(group)` helper. Validation behavior unchanged — pure
   metadata addition, `test_settings_groups.py` created to pin it.
2. **Nine appearance + voice keys** (`14ffe85`) — four `appearance` keys
   (`theme`, `ui_density`, `font_scale`, `accent`) and five `voice` keys
   (`voice_lang`, `voice_name`, `voice_rate`, `voice_pitch`, `auto_speak`),
   each with a validator and a default. `EDITABLE_KEYS` grew from 11 to 20.
3. **`ModelResolver` for call-time model-id resolution** (`a7cf586`,
   `619c907`, `2daf34e`) — new `preferences/resolver.py`: `ModelResolver(store,
   settings).resolve(key)` reads a preference override at call time instead of a
   frozen constructor value, with a `Settings` fallback and a `KeyError` guard
   for unknown keys. Threaded a `resolver=None`-default keyword through
   `CascadeResponder`, `SkillEngine`, `AgentRegistry`, `VisionOCR`, and all four
   `create_app()` construction sites in `main.py`, so `resolver=None` stays
   byte-identical to pre-change behavior. Registered five new `model`-group
   keys: `persona_model`, `technical_model`, `artifact_model`, `vision_model`,
   `agent_default_model` — `EDITABLE_KEYS` reached 25.
   This task took **two follow-up fix passes** after the first review proved by
   mutation that the wiring itself was untested: reverting all four
   `CascadeResponder`/`SkillEngine`/`VisionOCR` call sites, or stripping every
   `resolver=model_resolver` argument from `main.py`, still passed the full
   suite. `619c907` added five wiring-pinning tests plus the `resolve()` key
   guard; `2daf34e` closed the remaining gap where `technical_model` and the
   delegated-cascade composition path were only exercised on the
   non-delegated early-return branch, adding
   `test_cascade_uses_resolver_for_technical_model_when_delegated`. See
   `logs/model-resolver_2026-07-27_log.md`,
   `logs/model-resolver-review-fixes_2026-07-27_log.md`, and
   `logs/model-resolver-mutation-fix_2026-07-27_log.md` for the detailed
   before/after mutation matrices.
4. **`PreferencesStore.reset` + `POST /api/settings/reset`** (`9ccfb12`) — new
   `reset(keys)` method on the store (deletes overrides, falls back to
   defaults), and a route that resets either a whole group (`{"group": "..."}`,
   resolved via `keys_in_group`) or an explicit key list (`{"keys": [...]}`),
   rejecting requests that supply both or neither with a 422.
5. **Read-only `locked` block** (this task) — `LOCKED_KEYS: tuple[str, ...]` in
   `routes/settings.py`, an explicit eight-name literal allowlist
   (`llm_provider`, `agent_tools_enabled`, `allow_shell_tools`,
   `allow_email_tools`, `allow_file_delete`,
   `require_confirmation_for_risky_tools`, `tool_confirm_threshold`,
   `max_tool_iterations`), added to `_payload()` as
   `"locked": {key: getattr(settings, key) for key in LOCKED_KEYS}`. Present on
   the `GET`, `PATCH`, and `POST /api/settings/reset` responses since all three
   share `_payload()`.

## Why
The new settings UI (sidebar-nav modal, new Appearance/Model/Voice/Data groups —
see `docs/superpowers/specs/2026-07-27-settings-overhaul-design.md`) needs a
backend that (a) knows which group each editable key belongs to so the UI can
partition and bulk-reset by group, (b) actually applies a saved model-id at call
time instead of requiring a process restart, and (c) can show the deployment's
safety posture (shell/email/file-delete tool flags, confirmation threshold)
without ever exposing a way to change it from the browser. Task 5 in particular
exists because the panel that displays these flags must not become the panel
that can flip them — `LOCKED_KEYS` is a literal tuple, never a filter over
`Settings` fields, so a future field addition cannot silently start leaking
(or, worse, silently start being displayed as safe-to-edit).

## Files touched
- `services/assistant-core/src/violet_assistant/preferences/store.py` —
  `PrefSpec`, `keys_in_group`, 14 new keys (appearance/voice) + 5 model keys,
  `reset()`.
- `services/assistant-core/src/violet_assistant/preferences/resolver.py` (new)
  — `ModelResolver`.
- `services/assistant-core/src/violet_assistant/orchestrator/cascade.py`,
  `skills/generator.py`, `agents/registry.py`, `ingestion/ocr.py`, `main.py` —
  threaded `resolver=None` param through.
- `services/assistant-core/src/violet_assistant/routes/settings.py` —
  `ResetRequest`, `POST /api/settings/reset`, `LOCKED_KEYS`, `locked` in
  `_payload()`.
- Tests: `tests/test_settings_groups.py` (tasks 1, 2, 4),
  `tests/test_model_resolver.py` (task 3, three passes),
  `tests/test_settings_locked.py` (new, task 5).

## Interfaces / contracts changed
- `EDITABLE_KEYS: dict[str, PrefSpec]` — 25 keys total, each tagged with a
  group (`general`, `appearance`, `model`, `behavior`, `voice`, `knowledge`).
- `keys_in_group(group: str) -> list[str]`.
- `ModelResolver(preferences: PreferencesStore | None, settings: Settings)` /
  `.resolve(key: str) -> str`, raises `KeyError` on an unknown key.
- `CascadeResponder`, `SkillEngine`, `AgentRegistry`, `VisionOCR` each gained a
  trailing `resolver=None` keyword; `None` preserves prior behavior exactly.
- `PreferencesStore.reset(keys: list[str]) -> None`.
- `POST /api/settings/reset` — body `{"group": str} | {"keys": list[str]}`
  (exactly one), 422 on both-or-neither or unknown group.
- `GET /api/settings`, `PATCH /api/settings`, `POST /api/settings/reset` all
  now return a `locked` key: `{key: getattr(settings, key) for key in
  LOCKED_KEYS}`, eight fixed names. `LOCKED_KEYS` is disjoint from
  `EDITABLE_KEYS` by construction (test-enforced) — a locked key can never
  become editable through this endpoint, and the allowlist contains no
  secret-shaped name (`api_key`, `base_url`, `token`, `secret`, `password`,
  `path`, `url` — test-enforced via a compiled forbidden-pattern check on every
  emitted key).
- No new env vars. No schema/migration change.

## Status
done — Phase A (tasks 1–5) complete.

## Verification
- Task 5 red: `python -m pytest services/assistant-core/tests/test_settings_locked.py -q`
  → `ImportError: cannot import name 'LOCKED_KEYS' from 'violet_assistant.routes.settings'`
  (collection error, as expected before implementation).
- Task 5 green: same command → **3 passed**.
- Full suite after task 5: `python -m pytest` (repo root) → **224 passed**, 8
  warnings, ~14–15s. (221 at branch start per task brief + 3 new in
  `test_settings_locked.py`.)
- Break-it verification performed before committing (each mutation applied to
  `routes/settings.py`, confirmed to fail, then reverted):
  1. Replaced the literal `LOCKED_KEYS` tuple with a naive derivation —
     `tuple(f.name for f in dataclasses.fields(Settings) if f.type == "bool" or
     f.name in {"llm_provider", "tool_confirm_threshold",
     "max_tool_iterations"})` — simulating "iterate Settings and filter"
     instead of an explicit allowlist. Result: **2 of 3 tests failed**.
     `test_locked_block_is_exactly_the_allowlist` caught the extra leaked keys
     (`memory_auto_save`, `memory_require_approval`, `knowledge_auto_sync`,
     `knowledge_scan_on_startup` — all boolean `Settings` fields that are not
     safety flags), and `test_locked_keys_are_not_editable` caught that three
     of those leaked keys are also in `EDITABLE_KEYS` (i.e. the naive filter
     would have displayed editable preferences as if they were locked safety
     flags, and vice versa risked the reverse). Reverted, suite green again.
  2. Dropped `max_tool_iterations` from the literal tuple (7 keys instead of
     8). Result: `test_locked_block_is_exactly_the_allowlist` **failed**
     (`Extra items in the right set: 'max_tool_iterations'`). Reverted, suite
     green again.
  - `git diff --stat` on `routes/settings.py` confirmed clean (no residual
    mutation) before the final commit.

## Next
- Phase B (backend data: session delete, export) and the frontend `DataPanel`
  (Task 15) consume `locked` from `GET /api/settings` to render the safety
  posture read-only.
- No validation yet that a locked value's *type* stays what the frontend
  expects (e.g. `tool_confirm_threshold` is a free-form string in `Settings`,
  not a checked enum) — acceptable for a read-only display, would matter if a
  locked field is ever surfaced through anything editable.
