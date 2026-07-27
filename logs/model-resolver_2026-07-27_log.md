# ModelResolver — live model-id overrides

- **Date:** 2026-07-27
- **Track:** cross-cutting (1 Chat + agents/skills/ingestion)
- **Branch:** feat/settings-overhaul
- **Author:** Claude Code (settings overhaul, task 3/18)

## What
Added `ModelResolver`, which resolves a model-id preference at call time with a `Settings`
fallback, and threaded it through the four components that previously held a frozen model
string (`CascadeResponder`, `SkillEngine`, `AgentRegistry`, `VisionOCR`). Registered five new
`model`-group preference keys: `persona_model`, `technical_model`, `artifact_model`,
`vision_model`, `agent_default_model`.

## Why
All five model ids were baked into their components at `create_app()` time. Once the settings
UI gains editable model-id fields, saving a new value would appear to succeed and change
nothing until a process restart. Components now hold the resolver and read the preference on
each call instead.

Only model **identifiers** are editable. The matching `*_base_url` / `*_api_key` fields, and
the `ALLOW_*` safety flags, stay frozen in `Settings` — model ids are not secrets, credentials
and endpoints are.

## Files touched
- `services/assistant-core/src/violet_assistant/preferences/resolver.py` (new)
- `services/assistant-core/src/violet_assistant/preferences/store.py` — 5 keys + 5 defaults
- `services/assistant-core/src/violet_assistant/orchestrator/cascade.py` — shared seam
- `services/assistant-core/src/violet_assistant/skills/generator.py`
- `services/assistant-core/src/violet_assistant/agents/registry.py`
- `services/assistant-core/src/violet_assistant/ingestion/ocr.py`
- `services/assistant-core/src/violet_assistant/main.py` — shared seam (4 construction sites)
- `services/assistant-core/tests/test_model_resolver.py` (new)

## Interfaces / contracts changed
- New: `ModelResolver(preferences: PreferencesStore | None, settings: Settings)` with
  `.resolve(key: str) -> str`. Blank/whitespace override falls back — never `model=""`.
- `CascadeResponder`, `SkillEngine`, `AgentRegistry`, `VisionOCR` each gained a trailing
  `resolver=None` keyword param. With `resolver=None` behavior is byte-identical to before.
- `EDITABLE_KEYS` grows 20 → 25 keys, all in the existing `model` group.
- No new env vars. No schema/migration change.

Design notes: the resolver deliberately does not cache — `PreferencesStore.effective()`
re-reads a small JSON file, which is what makes a save take effect on the next request.
`CascadeResponder.respond()` binds `persona_model`/`technical_model` once at the top so a
mid-turn edit cannot make the three persona calls in one turn disagree. `AgentRegistry.list_agents()`
resolves once per listing for the same reason. `VisionOCR` builds a raw request body rather
than `LLMOptions`, so the resolved id goes into the payload dict inside `_ocr_sync` — on the
worker thread, keeping the file read off the event loop.

## Status
done

## Verification
- `python -m pytest services/assistant-core/tests/test_model_resolver.py -q` → failed first with
  `ModuleNotFoundError: No module named 'violet_assistant.preferences.resolver'` (expected, TDD red).
- Same command after implementation → **6 passed**.
- `python -m pytest` (repo root) → **207 passed**, 4 warnings, 13.02s. Baseline was 201; no
  existing test modified.

## Next
- Settings UI fields for the five model ids (later task in the overhaul).
- Consider a `typing.Protocol` for the `resolver` params so the four leaf modules can be typed
  without importing the preferences package.
- No validation that a model id actually exists — a typo saves cleanly and surfaces as a
  provider-side 400. Consistent with the pre-existing `llm_model` / `web_search_model` keys,
  but worth an error-surfacing story once the UI accepts free text.
