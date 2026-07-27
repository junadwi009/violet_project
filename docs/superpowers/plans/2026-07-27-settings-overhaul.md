# Settings Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 500-line single-column settings modal with a sidebar-nav panel of nine focused groups, add Appearance / Model / Voice / Data groups with the 14 preference keys they need, and fix the persistence, write-amplification, and accessibility defects in the same pass.

**Architecture:** The backend `PreferencesStore` gains per-key `group` metadata (enabling reset-by-section), fourteen new keys, a `ModelResolver` so model-id overrides take effect without an app restart, and four new endpoints. The frontend splits `SettingsModal.tsx` into a shell plus nine panel components, with theme applied via CSS custom-property overrides on `<html>`.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, SQLite, pytest. React 19, TypeScript 5.9 (strict), Vite 7, Tailwind CSS v4 (`@theme` tokens), lucide-react.

## Global Constraints

- **Security boundary is absolute.** API keys (`*_api_key`), base URLs (`*_base_url`), filesystem/DB paths, and the `ALLOW_*` safety flags stay in frozen `Settings` / `.env`. They are never added to `EDITABLE_KEYS`. The `locked` block displays a fixed allowlist of eight names and is built from that literal tuple, never by filtering `Settings`.
- **Backend is TDD.** Write the failing test, run it, see it fail, implement, see it pass, commit. Every backend task follows this cycle.
- **Frontend has no test runner.** The web client ships no test framework and this plan does not add one. Frontend verification is `npm run build` (which runs `tsc -b` in strict mode, so type errors are real failures) plus explicit browser checks. Each frontend task lists its browser checks concretely.
- **Run backend tests from the repo root:** `python -m pytest` (pytest is configured with `.tmp/pytest` as basetemp).
- **Run frontend build from `apps/web-client`:** `npm run build`.
- **Every task ends in a commit.** Commit messages use the repo's existing `feat:` / `fix:` / `refactor:` / `docs:` prefixes.
- **The log rule is mandatory.** `CLAUDE.md` requires an entry in `logs/{Update}_{Date}_log.md` before committing. This plan writes one log file, `logs/settings-overhaul_2026-07-27_log.md`, updated in Task 18. Individual task commits do not each need their own log file — the design-phase log already exists and Task 18 records the implementation.
- **Preserve existing behavior when extracting.** Tasks 11's panel extraction must not change what any existing control does. New behavior arrives in Tasks 12–16.

## Deviations from the spec

Two, both deliberate, both to be confirmed by the user before Task 6:

1. **`delete_session` also deletes `agent_runs` for that session.** The spec listed three cascade steps (candidates, messages, session). `agent_runs` also carries `session_id` and holds resumable agent state; leaving orphaned runs after "clear all sessions" means paused runs pointing at conversations that no longer exist. `tool_audit_logs` remain untouched as the spec requires — those are the audit trail.
2. **`agent_default_model` is live-resolvable only because `AgentRegistry.list_agents()` re-parses from disk on every call** (`agents/registry.py:17`). This was verified, not assumed. If that ever caches, the setting silently stops working — Task 3 adds a test that pins the behavior.

---

## File Structure

**Backend — created:**

| File | Responsibility |
|---|---|
| `services/assistant-core/src/violet_assistant/preferences/resolver.py` | `ModelResolver` — one job: resolve a model-id pref at call time with a `Settings` fallback |
| `services/assistant-core/src/violet_assistant/routes/export.py` | `GET /api/export` bundle assembly |
| `services/assistant-core/tests/test_settings_groups.py` | group metadata + reset endpoint |
| `services/assistant-core/tests/test_settings_locked.py` | locked-block allowlist, incl. the no-secrets assertion |
| `services/assistant-core/tests/test_model_resolver.py` | resolver fallback + live-override reachability |
| `services/assistant-core/tests/test_sessions_delete.py` | cascade delete |
| `services/assistant-core/tests/test_export.py` | bundle contents + secret exclusion |

**Backend — modified:** `preferences/store.py` (PrefSpec + 14 keys), `routes/settings.py` (reset + locked), `routes/sessions.py` (DELETE), `persistence/sqlite_store.py` (delete methods), `main.py` (resolver wiring, export router), `orchestrator/cascade.py`, `skills/generator.py`, `agents/registry.py`, `documents/` VisionOCR call site.

**Frontend — created:** `components/settings/` — `SettingsShell.tsx`, `SettingsPanel.tsx`, `SettingsNav.tsx`, `useDebouncedPatch.ts`, 5 files under `controls/`, 9 under `panels/` (18 files) — plus `lib/theme.ts`.

**Frontend — modified:** `lib/api.ts`, `lib/speech.ts`, `App.tsx`, `index.css`, `index.html`. **Deleted:** `components/SettingsModal.tsx`.

---

# Phase A — Backend preferences

## Task 1: Group metadata on preference keys

**Files:**
- Modify: `services/assistant-core/src/violet_assistant/preferences/store.py`
- Test: `services/assistant-core/tests/test_settings_groups.py` (create)

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `PrefSpec(validate: Callable[[Any], bool], group: str)` frozen dataclass; `EDITABLE_KEYS: dict[str, PrefSpec]`; `GROUPS: tuple[str, ...]`; `keys_in_group(group: str) -> list[str]`. `PreferencesStore.effective/defaults/patch/overridden` signatures are unchanged.

This is a pure refactor — no key is added, removed, or revalidated differently. It exists so Task 4 can reset a section and the UI can show a per-section modified dot.

- [ ] **Step 1: Write the failing test**

Create `services/assistant-core/tests/test_settings_groups.py`:

```python
from __future__ import annotations

import pytest

from violet_assistant.config import load_settings
from violet_assistant.preferences.store import (
    EDITABLE_KEYS,
    GROUPS,
    PreferencesStore,
    keys_in_group,
)


@pytest.fixture()
def settings(tmp_path):
    return load_settings(tmp_path)


def test_every_key_declares_a_known_group():
    for key, spec in EDITABLE_KEYS.items():
        assert spec.group in GROUPS, f"{key} has unknown group {spec.group!r}"


def test_keys_in_group_partitions_all_keys():
    seen: set[str] = set()
    for group in GROUPS:
        keys = keys_in_group(group)
        assert keys, f"group {group!r} has no keys"
        seen.update(keys)
    assert seen == set(EDITABLE_KEYS)


def test_keys_in_group_rejects_unknown_group():
    with pytest.raises(KeyError):
        keys_in_group("nope")


def test_validation_still_works_after_refactor(tmp_path, settings):
    store = PreferencesStore(tmp_path / "preferences.json")
    store.patch({"temperature": 0.9})
    assert store.effective(settings)["temperature"] == 0.9
    with pytest.raises(ValueError):
        store.patch({"temperature": 5.0})
    with pytest.raises(ValueError):
        store.patch({"llm_api_key": "sk-nope"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/assistant-core/tests/test_settings_groups.py -q`
Expected: FAIL — `ImportError: cannot import name 'GROUPS'`.

- [ ] **Step 3: Implement**

In `services/assistant-core/src/violet_assistant/preferences/store.py`, replace the imports, helper block, and `EDITABLE_KEYS` (lines 1–41) with:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from violet_assistant.config import Settings

# Editable keys map to a validator plus the settings group they render under. NO
# secrets here — API keys, base URLs, DB paths, and the ALLOW_* safety toggles
# stay in the frozen Settings / .env.


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _num(lo: float, hi: float) -> Callable[[Any], bool]:
    return (
        lambda value: isinstance(value, (int, float))
        and not isinstance(value, bool)
        and lo <= value <= hi
    )


def _is_str(value: Any) -> bool:
    return isinstance(value, str) and len(value) <= 200


def _choice(*allowed: str) -> Callable[[Any], bool]:
    options = set(allowed)
    return lambda value: value in options


@dataclass(frozen=True)
class PrefSpec:
    validate: Callable[[Any], bool]
    group: str


# Task 2 adds "appearance" and "voice" here, together with the keys that fill
# them — a group with no keys would fail the partition test.
GROUPS: tuple[str, ...] = ("general", "model", "behavior", "knowledge")


EDITABLE_KEYS: dict[str, PrefSpec] = {
    # general
    "ui_mode": PrefSpec(_choice("user", "developer"), "general"),
    "default_personality": PrefSpec(_is_str, "general"),
    "default_provider": PrefSpec(_is_str, "general"),
    # model
    "llm_model": PrefSpec(_is_str, "model"),
    "temperature": PrefSpec(_num(0.0, 2.0), "model"),
    "web_search_model": PrefSpec(_is_str, "model"),
    # behavior
    "memory_require_approval": PrefSpec(_is_bool, "behavior"),
    "memory_auto_save": PrefSpec(_is_bool, "behavior"),
    "web_search_enabled": PrefSpec(_is_bool, "behavior"),
    "canvas_enabled": PrefSpec(_is_bool, "behavior"),
    # knowledge
    "knowledge_auto_sync": PrefSpec(_is_bool, "knowledge"),
}


def keys_in_group(group: str) -> list[str]:
    if group not in GROUPS:
        raise KeyError(group)
    return [key for key, spec in EDITABLE_KEYS.items() if spec.group == group]
```

Then update `patch()` — change the validation line from `if not EDITABLE_KEYS[key](value):` to:

```python
            if not EDITABLE_KEYS[key].validate(value):
```

`_defaults()` and the rest of `PreferencesStore` are unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest services/assistant-core/tests/test_settings_groups.py services/assistant-core/tests/test_preferences.py -q`
Expected: PASS — 4 new + 8 existing. The existing suite must stay green; it exercises `patch()` through the same code path.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass. Any failure here means something else imported `EDITABLE_KEYS` expecting callables — fix that call site before committing.

- [ ] **Step 6: Commit**

```bash
git add services/assistant-core/src/violet_assistant/preferences/store.py services/assistant-core/tests/test_settings_groups.py
git commit -m "refactor: give preference keys group metadata"
```

---

## Task 2: Appearance and voice preference keys

**Files:**
- Modify: `services/assistant-core/src/violet_assistant/preferences/store.py`
- Test: `services/assistant-core/tests/test_settings_groups.py`

**Interfaces:**
- Consumes: `PrefSpec`, `GROUPS`, `keys_in_group` from Task 1.
- Produces: nine new keys — `theme`, `ui_density`, `font_scale`, `accent` (group `appearance`); `voice_lang`, `voice_name`, `voice_rate`, `voice_pitch`, `auto_speak` (group `voice`). Frontend Tasks 12 and 14 read these names.

- [ ] **Step 1: Write the failing test**

Append to `services/assistant-core/tests/test_settings_groups.py`:

```python
def test_appearance_defaults(tmp_path, settings):
    values = PreferencesStore(tmp_path / "preferences.json").effective(settings)
    assert values["theme"] == "system"
    assert values["ui_density"] == "cozy"
    assert values["font_scale"] == 1.0
    assert values["accent"] == "violet"


def test_voice_defaults(tmp_path, settings):
    values = PreferencesStore(tmp_path / "preferences.json").effective(settings)
    assert values["voice_lang"] == "id-ID"
    assert values["voice_name"] == ""
    assert values["voice_rate"] == 1.0
    assert values["voice_pitch"] == 1.0
    assert values["auto_speak"] is False


@pytest.mark.parametrize(
    ("key", "good", "bad"),
    [
        ("theme", "dark", "neon"),
        ("ui_density", "compact", "airy"),
        ("font_scale", 1.25, 3.0),
        ("accent", "teal", "#ff0000"),
        ("voice_rate", 0.5, 0.1),
        ("voice_pitch", 2.0, 2.5),
        ("auto_speak", True, "yes"),
    ],
)
def test_new_keys_validate(tmp_path, settings, key, good, bad):
    store = PreferencesStore(tmp_path / "preferences.json")
    store.patch({key: good})
    assert store.effective(settings)[key] == good
    with pytest.raises(ValueError):
        store.patch({key: bad})


def test_font_scale_rejects_bool(tmp_path):
    # bool is a subclass of int; _num must not accept it
    store = PreferencesStore(tmp_path / "preferences.json")
    with pytest.raises(ValueError):
        store.patch({"font_scale": True})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/assistant-core/tests/test_settings_groups.py -q`
Expected: FAIL — `KeyError: 'theme'` from `effective()`.

- [ ] **Step 3: Implement**

In `store.py`, extend `GROUPS`:

```python
GROUPS: tuple[str, ...] = (
    "general",
    "appearance",
    "model",
    "behavior",
    "voice",
    "knowledge",
)
```

Add to `EDITABLE_KEYS`, after the `general` block:

```python
    # appearance
    "theme": PrefSpec(_choice("light", "dark", "system"), "appearance"),
    "ui_density": PrefSpec(_choice("cozy", "compact"), "appearance"),
    "font_scale": PrefSpec(_num(0.875, 1.25), "appearance"),
    "accent": PrefSpec(
        _choice("violet", "indigo", "teal", "amber", "rose"), "appearance"
    ),
```

and after the `behavior` block:

```python
    # voice
    "voice_lang": PrefSpec(_is_str, "voice"),
    "voice_name": PrefSpec(_is_str, "voice"),
    "voice_rate": PrefSpec(_num(0.5, 2.0), "voice"),
    "voice_pitch": PrefSpec(_num(0.0, 2.0), "voice"),
    "auto_speak": PrefSpec(_is_bool, "voice"),
```

Add to the dict returned by `_defaults()`:

```python
        "theme": "system",
        "ui_density": "cozy",
        "font_scale": 1.0,
        "accent": "violet",
        "voice_lang": "id-ID",
        "voice_name": "",
        "voice_rate": 1.0,
        "voice_pitch": 1.0,
        "auto_speak": False,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest services/assistant-core/tests/ -q -k "settings or preferences"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/assistant-core/src/violet_assistant/preferences/store.py services/assistant-core/tests/test_settings_groups.py
git commit -m "feat: appearance and voice preference keys"
```

---

## Task 3: ModelResolver and live model-id overrides

**Files:**
- Create: `services/assistant-core/src/violet_assistant/preferences/resolver.py`
- Modify: `services/assistant-core/src/violet_assistant/preferences/store.py`, `orchestrator/cascade.py`, `skills/generator.py`, `agents/registry.py`, `main.py`
- Test: `services/assistant-core/tests/test_model_resolver.py` (create)

**Interfaces:**
- Consumes: `PreferencesStore`, `PrefSpec` from Tasks 1–2.
- Produces: `ModelResolver(preferences: PreferencesStore | None, settings: Settings)` with `.resolve(key: str) -> str`. Five new keys: `persona_model`, `technical_model`, `artifact_model`, `vision_model`, `agent_default_model` (all group `model`).

**Why a resolver:** all five model ids are currently baked into components at `create_app()` time (`main.py:110`, `:130`, `:164`, `:205`). Saving a new value would appear to work and change nothing until restart. Components take the resolver and read at call time instead.

- [ ] **Step 1: Write the failing test**

Create `services/assistant-core/tests/test_model_resolver.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from violet_assistant.agents.registry import AgentRegistry
from violet_assistant.config import load_settings
from violet_assistant.preferences.resolver import ModelResolver
from violet_assistant.preferences.store import PreferencesStore


@pytest.fixture()
def settings(tmp_path):
    return load_settings(tmp_path)


def test_resolve_falls_back_to_settings(tmp_path, settings):
    store = PreferencesStore(tmp_path / "preferences.json")
    resolver = ModelResolver(store, settings)
    assert resolver.resolve("persona_model") == settings.persona_model


def test_resolve_prefers_override(tmp_path, settings):
    store = PreferencesStore(tmp_path / "preferences.json")
    store.patch({"persona_model": "meta-llama/llama-3.3-70b"})
    resolver = ModelResolver(store, settings)
    assert resolver.resolve("persona_model") == "meta-llama/llama-3.3-70b"


def test_blank_override_falls_back(tmp_path, settings):
    # An emptied text field must not send model="" to the provider.
    store = PreferencesStore(tmp_path / "preferences.json")
    store.patch({"persona_model": "   "})
    resolver = ModelResolver(store, settings)
    assert resolver.resolve("persona_model") == settings.persona_model


def test_resolve_without_preferences(settings):
    assert ModelResolver(None, settings).resolve("vision_model") == settings.vision_model


def test_override_is_read_per_call(tmp_path, settings):
    # The resolver must not cache: editing prefs takes effect without a restart.
    store = PreferencesStore(tmp_path / "preferences.json")
    resolver = ModelResolver(store, settings)
    assert resolver.resolve("artifact_model") == settings.artifact_model
    store.patch({"artifact_model": "qwen/qwen3-max"})
    assert resolver.resolve("artifact_model") == "qwen/qwen3-max"


def test_agent_registry_uses_resolver_per_call(tmp_path, settings):
    agents_dir = tmp_path / "agents"
    (agents_dir / "demo").mkdir(parents=True)
    (agents_dir / "demo" / "SKILL.md").write_text(
        "---\nname: Demo\ndescription: demo agent\n---\n\nBody.\n",
        encoding="utf-8",
    )
    store = PreferencesStore(tmp_path / "preferences.json")
    resolver = ModelResolver(store, settings)
    registry = AgentRegistry(agents_dir, resolver=resolver)

    assert registry.list_agents()[0].model == settings.agent_default_model
    store.patch({"agent_default_model": "openai/gpt-oss-120b"})
    # No restart, no cache: the next call reflects the new default.
    assert registry.list_agents()[0].model == "openai/gpt-oss-120b"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/assistant-core/tests/test_model_resolver.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'violet_assistant.preferences.resolver'`.

- [ ] **Step 3: Add the five model keys**

In `store.py`, add to the `model` block of `EDITABLE_KEYS`:

```python
    "persona_model": PrefSpec(_is_str, "model"),
    "technical_model": PrefSpec(_is_str, "model"),
    "artifact_model": PrefSpec(_is_str, "model"),
    "vision_model": PrefSpec(_is_str, "model"),
    "agent_default_model": PrefSpec(_is_str, "model"),
```

and to `_defaults()`:

```python
        "persona_model": settings.persona_model,
        "technical_model": settings.technical_model,
        "artifact_model": settings.artifact_model,
        "vision_model": settings.vision_model,
        "agent_default_model": settings.agent_default_model,
```

- [ ] **Step 4: Create the resolver**

Create `services/assistant-core/src/violet_assistant/preferences/resolver.py`:

```python
from __future__ import annotations

from violet_assistant.config import Settings
from violet_assistant.preferences.store import PreferencesStore


class ModelResolver:
    """Resolve a model-id preference at call time, falling back to ``Settings``.

    Components hold this instead of a frozen model string so that editing a model
    id in the settings UI takes effect on the next request rather than the next
    restart. Deliberately does not cache — ``PreferencesStore.effective`` re-reads
    a small JSON file, which is cheap relative to the LLM call it precedes.
    """

    def __init__(self, preferences: PreferencesStore | None, settings: Settings) -> None:
        self._preferences = preferences
        self._settings = settings

    def resolve(self, key: str) -> str:
        fallback = getattr(self._settings, key)
        if self._preferences is None:
            return fallback
        value = self._preferences.effective(self._settings).get(key)
        # A blank override means "unset" — never send model="" to a provider.
        if isinstance(value, str) and value.strip():
            return value
        return fallback
```

- [ ] **Step 5: Wire CascadeResponder**

In `orchestrator/cascade.py`, add `resolver` to `__init__` and replace the three `self.persona.model` / `self.technical.model` reads.

Change the constructor signature and body:

```python
    def __init__(
        self,
        persona: LayerConfig,
        technical: LayerConfig,
        timeout_seconds: float = 120,
        provider_factory=None,
        resolver=None,
    ) -> None:
        self.persona = persona
        self.technical = technical
        self._make = provider_factory or self._default_provider_factory
        self.timeout_seconds = timeout_seconds
        self._resolver = resolver
        self._persona_provider = self._make(persona)
        self._technical_provider = self._make(technical)

    def _persona_model(self) -> str:
        if self._resolver is None:
            return self.persona.model
        return self._resolver.resolve("persona_model")

    def _technical_model(self) -> str:
        if self._resolver is None:
            return self.technical.model
        return self._resolver.resolve("technical_model")
```

In `respond()`, bind both once at the top so a mid-turn edit cannot make the three persona calls disagree:

```python
    async def respond(
        self, messages: Sequence[Message], base_options: LLMOptions
    ) -> CascadeResult:
        persona_model = self._persona_model()
        technical_model = self._technical_model()
        persona_messages = self._with_delegation_instruction(messages)
        first = await self._persona_provider.chat(
            persona_messages,
            LLMOptions(model=persona_model, temperature=base_options.temperature),
        )
```

Then replace every remaining `self.persona.model` with `persona_model` and `self.technical.model` with `technical_model` in the rest of `respond()` — there are three more occurrences (the early-return `models_used`, the technical `LLMOptions`, the composed `LLMOptions`, and the final `models_used`).

- [ ] **Step 6: Wire SkillEngine, AgentRegistry, VisionOCR**

In `skills/generator.py`, change `__init__` to accept a resolver and read at call time:

```python
    def __init__(self, provider: LLMProvider, model: str, resolver=None) -> None:
        self.provider = provider
        self.model = model
        self._resolver = resolver

    def _effective_model(self) -> str:
        if self._resolver is None:
            return self.model
        return self._resolver.resolve("artifact_model")
```

and at line 102 replace `LLMOptions(model=self.model, temperature=0.2)` with `LLMOptions(model=self._effective_model(), temperature=0.2)`.

> Keep the existing `self.provider = provider` assignment exactly as it is in the file; only the `resolver` parameter and `_effective_model` are new.

In `agents/registry.py`:

```python
class AgentRegistry:
    def __init__(
        self,
        config_dir: Path,
        default_model: str = "nousresearch/hermes-4-70b",
        resolver=None,
    ) -> None:
        self.config_dir = config_dir
        self.default_model = default_model
        self._resolver = resolver

    def _effective_default_model(self) -> str:
        if self._resolver is None:
            return self.default_model
        return self._resolver.resolve("agent_default_model")
```

and in `list_agents()` replace `default_model=self.default_model` with `default_model=self._effective_default_model()`.

In `main.py`, build the resolver right after `preferences` (line 59) and pass it to the four construction sites:

```python
    preferences = PreferencesStore(active_settings.repo_root / "data" / "preferences.json")
    model_resolver = ModelResolver(preferences, active_settings)
```

with the import `from violet_assistant.preferences.resolver import ModelResolver` added beside the existing `PreferencesStore` import (line 34). Then:

- line 111 — add `resolver=model_resolver,` to the `CascadeResponder(...)` call.
- line 130 — add `resolver=model_resolver,` to the `SkillEngine(...)` call.
- line 163 — `agent_registry = AgentRegistry(agents_dir, default_model=active_settings.agent_default_model, resolver=model_resolver)`.
- line 202 — `VisionOCR` takes a frozen `model=`. Give it the same treatment: add a `resolver=None` parameter and an `_effective_model()` returning `self._resolver.resolve("vision_model")` when set, use it at the point the model is put into `LLMOptions`, and pass `resolver=model_resolver` here.

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest services/assistant-core/tests/test_model_resolver.py -q`
Expected: PASS — 6 tests.

- [ ] **Step 8: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass. The cascade and agent tests exercise the modified constructors with `resolver=None`, which must behave exactly as before.

- [ ] **Step 9: Commit**

```bash
git add services/assistant-core/src/violet_assistant/preferences/ services/assistant-core/src/violet_assistant/orchestrator/cascade.py services/assistant-core/src/violet_assistant/skills/generator.py services/assistant-core/src/violet_assistant/agents/registry.py services/assistant-core/src/violet_assistant/main.py services/assistant-core/tests/test_model_resolver.py
git commit -m "feat: resolve model ids from preferences at call time"
```

---

## Task 4: Reset endpoint

**Files:**
- Modify: `services/assistant-core/src/violet_assistant/preferences/store.py`, `routes/settings.py`
- Test: `services/assistant-core/tests/test_settings_groups.py`

**Interfaces:**
- Consumes: `keys_in_group` (Task 1), `PreferencesStore` (Tasks 1–3).
- Produces: `PreferencesStore.reset(keys: list[str]) -> dict[str, Any]`; `POST /api/settings/reset` accepting `{"group": str}` **or** `{"keys": [str]}`, returning the same `{values, defaults, overridden}` payload as `GET`. Frontend Task 10's `SectionHeader` calls this.

- [ ] **Step 1: Write the failing test**

Append to `services/assistant-core/tests/test_settings_groups.py`:

```python
from fastapi import HTTPException

from violet_assistant.routes.settings import ResetRequest, create_settings_router


def _reset_endpoint(router):
    for route in router.routes:
        if route.path == "/api/settings/reset":
            return route.endpoint
    raise KeyError("reset")


def test_store_reset_removes_only_named_keys(tmp_path, settings):
    store = PreferencesStore(tmp_path / "preferences.json")
    store.patch({"temperature": 0.9, "theme": "dark", "canvas_enabled": False})
    store.reset(["temperature"])
    values = store.effective(settings)
    assert values["temperature"] == settings.default_temperature
    assert values["theme"] == "dark"
    assert set(store.overridden()) == {"theme", "canvas_enabled"}


def test_store_reset_is_idempotent(tmp_path, settings):
    store = PreferencesStore(tmp_path / "preferences.json")
    store.reset(["temperature"])
    assert store.overridden() == []


@pytest.mark.asyncio
async def test_reset_by_group(tmp_path, settings):
    store = PreferencesStore(tmp_path / "preferences.json")
    store.patch({"theme": "dark", "font_scale": 1.25, "temperature": 0.9})
    router = create_settings_router(store, settings)

    body = await _reset_endpoint(router)(ResetRequest(group="appearance"))
    assert body["values"]["theme"] == "system"
    assert body["values"]["font_scale"] == 1.0
    # a different group is untouched
    assert body["values"]["temperature"] == 0.9
    assert body["overridden"] == ["temperature"]


@pytest.mark.asyncio
async def test_reset_by_keys(tmp_path, settings):
    store = PreferencesStore(tmp_path / "preferences.json")
    store.patch({"theme": "dark", "font_scale": 1.25})
    router = create_settings_router(store, settings)

    body = await _reset_endpoint(router)(ResetRequest(keys=["theme"]))
    assert body["values"]["theme"] == "system"
    assert body["values"]["font_scale"] == 1.25


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        ResetRequest(),
        ResetRequest(group="appearance", keys=["theme"]),
        ResetRequest(group="nope"),
        ResetRequest(keys=["llm_api_key"]),
    ],
)
async def test_reset_rejects_bad_requests(tmp_path, settings, payload):
    store = PreferencesStore(tmp_path / "preferences.json")
    router = create_settings_router(store, settings)
    with pytest.raises(HTTPException) as exc_info:
        await _reset_endpoint(router)(payload)
    assert exc_info.value.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/assistant-core/tests/test_settings_groups.py -q -k reset`
Expected: FAIL — `ImportError: cannot import name 'ResetRequest'`.

- [ ] **Step 3: Add `reset` to the store**

Append to `PreferencesStore` in `store.py`:

```python
    def reset(self, keys: list[str]) -> dict[str, Any]:
        """Drop the named overrides so ``effective`` falls back to Settings."""
        for key in keys:
            if key not in EDITABLE_KEYS:
                raise ValueError(f"unknown or non-editable key: {key}")
        current = {
            key: value for key, value in self._load().items() if key not in keys
        }
        current = {key: value for key, value in current.items() if key in EDITABLE_KEYS}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        return current
```

- [ ] **Step 4: Add the route**

In `routes/settings.py`, add the import and request model:

```python
from violet_assistant.preferences.store import PreferencesStore, keys_in_group


class ResetRequest(BaseModel):
    group: str | None = None
    keys: list[str] | None = None
```

and inside `create_settings_router`, before `return router`:

```python
    @router.post("/api/settings/reset")
    async def reset_settings(payload: ResetRequest) -> dict:
        if (payload.group is None) == (payload.keys is None):
            raise HTTPException(
                status_code=422, detail="provide exactly one of 'group' or 'keys'"
            )
        try:
            targets = (
                keys_in_group(payload.group)
                if payload.group is not None
                else list(payload.keys or [])
            )
            store.reset(targets)
        except KeyError as exc:
            raise HTTPException(
                status_code=422, detail=f"unknown group: {payload.group}"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _payload()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest services/assistant-core/tests/test_settings_groups.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/assistant-core/src/violet_assistant/preferences/store.py services/assistant-core/src/violet_assistant/routes/settings.py services/assistant-core/tests/test_settings_groups.py
git commit -m "feat: reset preferences by group or key"
```

---

## Task 5: Read-only locked block

**Files:**
- Modify: `services/assistant-core/src/violet_assistant/routes/settings.py`
- Test: `services/assistant-core/tests/test_settings_locked.py` (create)

**Interfaces:**
- Consumes: `create_settings_router` (Task 4).
- Produces: `LOCKED_KEYS: tuple[str, ...]` in `routes/settings.py`; a `locked` key on every `/api/settings` response. Frontend Task 15's `DataPanel` reads it.

- [ ] **Step 1: Write the failing test**

Create `services/assistant-core/tests/test_settings_locked.py`:

```python
from __future__ import annotations

import re

import pytest

from violet_assistant.config import load_settings
from violet_assistant.preferences.store import EDITABLE_KEYS, PreferencesStore
from violet_assistant.routes.settings import LOCKED_KEYS, create_settings_router


@pytest.fixture()
def settings(tmp_path):
    return load_settings(tmp_path)


def _get(router):
    for route in router.routes:
        if route.path == "/api/settings" and "GET" in route.methods:
            return route.endpoint
    raise KeyError("GET /api/settings")


@pytest.mark.asyncio
async def test_locked_block_is_exactly_the_allowlist(tmp_path, settings):
    router = create_settings_router(
        PreferencesStore(tmp_path / "preferences.json"), settings
    )
    body = await _get(router)()
    assert set(body["locked"]) == set(LOCKED_KEYS)
    assert set(LOCKED_KEYS) == {
        "llm_provider",
        "agent_tools_enabled",
        "allow_shell_tools",
        "allow_email_tools",
        "allow_file_delete",
        "require_confirmation_for_risky_tools",
        "tool_confirm_threshold",
        "max_tool_iterations",
    }


@pytest.mark.asyncio
async def test_locked_block_never_leaks_secrets(tmp_path, settings):
    router = create_settings_router(
        PreferencesStore(tmp_path / "preferences.json"), settings
    )
    body = await _get(router)()
    forbidden = re.compile(r"api_key|base_url|token|secret|password|path|url", re.I)
    for key in body["locked"]:
        assert not forbidden.search(key), f"{key} must not be exposed"


def test_locked_keys_are_not_editable():
    # A key must never be both displayed as locked and editable.
    assert set(LOCKED_KEYS).isdisjoint(EDITABLE_KEYS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/assistant-core/tests/test_settings_locked.py -q`
Expected: FAIL — `ImportError: cannot import name 'LOCKED_KEYS'`.

- [ ] **Step 3: Implement**

In `routes/settings.py`, add above `create_settings_router`:

```python
# Safety-relevant settings shown read-only in the UI. An explicit allowlist, never
# a filter over Settings — a filter silently starts leaking the moment someone adds
# a field whose name it did not anticipate.
LOCKED_KEYS: tuple[str, ...] = (
    "llm_provider",
    "agent_tools_enabled",
    "allow_shell_tools",
    "allow_email_tools",
    "allow_file_delete",
    "require_confirmation_for_risky_tools",
    "tool_confirm_threshold",
    "max_tool_iterations",
)
```

and extend `_payload()`:

```python
    def _payload() -> dict:
        return {
            "values": store.effective(settings),
            "defaults": store.defaults(settings),
            "overridden": store.overridden(),
            "locked": {key: getattr(settings, key) for key in LOCKED_KEYS},
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest services/assistant-core/tests/test_settings_locked.py -q`
Expected: PASS — 3 tests.

- [ ] **Step 5: Commit**

```bash
git add services/assistant-core/src/violet_assistant/routes/settings.py services/assistant-core/tests/test_settings_locked.py
git commit -m "feat: expose safety flags read-only on /api/settings"
```

---

# Phase B — Backend data

## Task 6: Session deletion with explicit cascade

**Files:**
- Modify: `services/assistant-core/src/violet_assistant/persistence/sqlite_store.py`, `routes/sessions.py`
- Test: `services/assistant-core/tests/test_sessions_delete.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `SQLiteStore.delete_session(session_id) -> dict[str, int]` (raises `KeyError` if absent) and `SQLiteStore.delete_all_sessions() -> dict[str, int]`. Both return `{"deleted_sessions", "deleted_messages", "deleted_candidates", "deleted_agent_runs"}`. Routes `DELETE /api/sessions/{session_id}` (404 if absent) and `DELETE /api/sessions`. Frontend Task 15 calls these.

**Cascade must be manual.** `database/migrations/001_init.sql` declares `FOREIGN KEY (session_id) REFERENCES sessions(id)` **without** `ON DELETE CASCADE`, and SQLite ignores foreign keys entirely unless `PRAGMA foreign_keys=ON` — which `SQLiteStore._connect` does not set. Deleting only the `sessions` row would orphan every message.

- [ ] **Step 1: Write the failing test**

Create `services/assistant-core/tests/test_sessions_delete.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from violet_assistant.memory.schema import MemoryCandidate
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.routes.sessions import create_sessions_router


@pytest.fixture()
def store(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    migration = repo_root / "database" / "migrations" / "001_init.sql"
    s = SQLiteStore(db_path=tmp_path / "test.db", migration_path=migration)
    s.initialize()
    return s


def _seed(store: SQLiteStore, session_id: str) -> str:
    store.ensure_session(session_id, title=f"title-{session_id}")
    message_id = store.add_message(session_id, role="user", content="hello")
    return message_id


def _endpoint(router, method: str, path: str):
    for route in router.routes:
        if route.path == path and method in route.methods:
            return route.endpoint
    raise KeyError(f"{method} {path}")


def test_delete_session_removes_messages(store):
    _seed(store, "s1")
    _seed(store, "s2")

    report = store.delete_session("s1")

    assert report["deleted_sessions"] == 1
    assert report["deleted_messages"] == 1
    assert [s["id"] for s in store.list_sessions()] == ["s2"]
    assert store.messages_for_session("s1") == []
    assert len(store.messages_for_session("s2")) == 1


def test_delete_session_removes_orphaned_candidates(store):
    message_id = _seed(store, "s1")
    store.add_memory_candidates(
        [
            MemoryCandidate(
                memory_type="fact",
                content="user likes tea",
                reason="stated",
                confidence=0.8,
                source_message_id=message_id,
            )
        ]
    )
    assert len(store.pending_memory_candidates()) == 1

    report = store.delete_session("s1")

    assert report["deleted_candidates"] == 1
    assert store.pending_memory_candidates() == []


def test_delete_session_preserves_audit_logs(store):
    _seed(store, "s1")
    store.add_tool_audit_log(
        tool="knowledge_search", args={"q": "x"}, result="ok", status="ok"
    )
    before = len(store.list_tool_audit_logs())

    store.delete_session("s1")

    assert len(store.list_tool_audit_logs()) == before


def test_delete_unknown_session_raises(store):
    with pytest.raises(KeyError):
        store.delete_session("missing")


def test_delete_all_sessions(store):
    _seed(store, "s1")
    _seed(store, "s2")

    report = store.delete_all_sessions()

    assert report["deleted_sessions"] == 2
    assert report["deleted_messages"] == 2
    assert store.list_sessions() == []


@pytest.mark.asyncio
async def test_delete_route_404_on_unknown(store):
    router = create_sessions_router(store)
    with pytest.raises(HTTPException) as exc_info:
        await _endpoint(router, "DELETE", "/api/sessions/{session_id}")("missing")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_routes_roundtrip(store):
    _seed(store, "s1")
    router = create_sessions_router(store)

    body = await _endpoint(router, "DELETE", "/api/sessions/{session_id}")("s1")
    assert body["deleted_sessions"] == 1

    _seed(store, "s2")
    body = await _endpoint(router, "DELETE", "/api/sessions")()
    assert body["deleted_sessions"] == 1
```

> **Before implementing:** run `python -m pytest services/assistant-core/tests/test_sessions_delete.py -q --collect-only` and confirm the `store` fixture resolves `001_init.sql`. If `parents[3]` is wrong for this layout, fix the fixture path — do not proceed with a broken fixture. Also confirm the real signatures of `add_message`, `add_tool_audit_log`, and `MemoryCandidate` against `sqlite_store.py` and `memory/schema.py`, and adjust the seed helpers to match; the assertions are the point, not the helper spellings.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/assistant-core/tests/test_sessions_delete.py -q`
Expected: FAIL — `AttributeError: 'SQLiteStore' object has no attribute 'delete_session'`.

- [ ] **Step 3: Implement the store methods**

Append to `SQLiteStore` in `persistence/sqlite_store.py`, next to `delete_memory`:

```python
    def delete_session(self, session_id: str) -> dict[str, int]:
        """Delete a session and everything scoped to it.

        The schema has no ON DELETE CASCADE and SQLite does not enforce foreign
        keys without PRAGMA foreign_keys=ON, so every child row is removed here
        explicitly. ``memories`` and ``tool_audit_logs`` are deliberately kept:
        an approved memory outlives the conversation that produced it, and an
        audit trail you can erase by clearing a chat is not an audit trail.
        """
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if exists is None:
                raise KeyError(session_id)
            candidates = connection.execute(
                """
                DELETE FROM memory_candidates
                WHERE source_message_id IN (
                  SELECT id FROM messages WHERE session_id = ?
                )
                """,
                (session_id,),
            ).rowcount
            runs = connection.execute(
                "DELETE FROM agent_runs WHERE session_id = ?", (session_id,)
            ).rowcount
            messages = connection.execute(
                "DELETE FROM messages WHERE session_id = ?", (session_id,)
            ).rowcount
            connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return {
            "deleted_sessions": 1,
            "deleted_messages": messages,
            "deleted_candidates": candidates,
            "deleted_agent_runs": runs,
        }

    def delete_all_sessions(self) -> dict[str, int]:
        with self._connect() as connection:
            sessions = connection.execute(
                "SELECT COUNT(*) AS n FROM sessions"
            ).fetchone()["n"]
            candidates = connection.execute(
                """
                DELETE FROM memory_candidates
                WHERE source_message_id IN (SELECT id FROM messages)
                """
            ).rowcount
            runs = connection.execute("DELETE FROM agent_runs").rowcount
            messages = connection.execute("DELETE FROM messages").rowcount
            connection.execute("DELETE FROM sessions")
        return {
            "deleted_sessions": sessions,
            "deleted_messages": messages,
            "deleted_candidates": candidates,
            "deleted_agent_runs": runs,
        }
```

- [ ] **Step 4: Implement the routes**

Replace `routes/sessions.py` with:

```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from violet_assistant.persistence.sqlite_store import SQLiteStore


def create_sessions_router(store: SQLiteStore) -> APIRouter:
    router = APIRouter()

    @router.get("/api/sessions")
    async def sessions() -> dict:
        return {"items": store.list_sessions()}

    @router.get("/api/sessions/{session_id}/messages")
    async def session_messages(session_id: str) -> dict:
        return {"items": store.messages_for_session(session_id)}

    @router.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str) -> dict:
        try:
            return store.delete_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc

    @router.delete("/api/sessions")
    async def delete_all_sessions() -> dict:
        return store.delete_all_sessions()

    return router
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest services/assistant-core/tests/test_sessions_delete.py -q`
Expected: PASS — 7 tests.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add services/assistant-core/src/violet_assistant/persistence/sqlite_store.py services/assistant-core/src/violet_assistant/routes/sessions.py services/assistant-core/tests/test_sessions_delete.py
git commit -m "feat: delete sessions with explicit cascade"
```

---

## Task 7: Export endpoint

**Files:**
- Create: `services/assistant-core/src/violet_assistant/routes/export.py`
- Modify: `services/assistant-core/src/violet_assistant/main.py`
- Test: `services/assistant-core/tests/test_export.py` (create)

**Interfaces:**
- Consumes: `SQLiteStore` (Task 6), `PreferencesStore` (Task 4), `ApprovedMemoryStore`.
- Produces: `create_export_router(store, memory_store, preferences, settings) -> APIRouter` serving `GET /api/export`. Frontend Task 15 links to it.

- [ ] **Step 1: Write the failing test**

Create `services/assistant-core/tests/test_export.py`:

```python
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from violet_assistant.config import load_settings
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.preferences.store import PreferencesStore
from violet_assistant.routes.export import create_export_router


class FakeMemoryStore:
    backend_name = "fake"

    def location(self) -> str:
        return "memory/"

    def list(self):
        return [{"id": "m1", "memory_type": "fact", "content": "likes tea"}]


@pytest.fixture()
def store(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    migration = repo_root / "database" / "migrations" / "001_init.sql"
    s = SQLiteStore(db_path=tmp_path / "test.db", migration_path=migration)
    s.initialize()
    s.ensure_session("s1", title="hello")
    s.add_message("s1", role="user", content="hi there")
    return s


def _get(router):
    for route in router.routes:
        if route.path == "/api/export":
            return route.endpoint
    raise KeyError("export")


@pytest.fixture()
def bundle_router(tmp_path, store):
    settings = load_settings(tmp_path)
    prefs = PreferencesStore(tmp_path / "preferences.json")
    prefs.patch({"theme": "dark"})
    return create_export_router(store, FakeMemoryStore(), prefs, settings)


@pytest.mark.asyncio
async def test_export_contains_user_data(bundle_router):
    response = await _get(bundle_router)()
    bundle = json.loads(response.body)

    assert bundle["schema_version"] == 1
    assert [s["id"] for s in bundle["sessions"]] == ["s1"]
    assert bundle["messages"][0]["content"] == "hi there"
    assert bundle["messages"][0]["session_id"] == "s1"
    assert bundle["memories"][0]["id"] == "m1"
    assert bundle["preferences"]["values"]["theme"] == "dark"
    assert bundle["preferences"]["overridden"] == ["theme"]


@pytest.mark.asyncio
async def test_export_is_an_attachment(bundle_router):
    response = await _get(bundle_router)()
    assert "attachment" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_export_excludes_locked_and_secrets(bundle_router):
    response = await _get(bundle_router)()
    bundle = json.loads(response.body)

    assert "locked" not in bundle
    assert "locked" not in bundle["preferences"]
    forbidden = re.compile(r"api_key|base_url|token|secret|password", re.I)
    assert not forbidden.search(response.body.decode("utf-8"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/assistant-core/tests/test_export.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'violet_assistant.routes.export'`.

- [ ] **Step 3: Implement**

Create `services/assistant-core/src/violet_assistant/routes/export.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Response

from violet_assistant.config import Settings
from violet_assistant.memory.store.base import ApprovedMemoryStore
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.preferences.store import PreferencesStore


def create_export_router(
    store: SQLiteStore,
    memory_store: ApprovedMemoryStore,
    preferences: PreferencesStore,
    settings: Settings,
) -> APIRouter:
    """A user-data backup: sessions, messages, memories, preference overrides.

    Deliberately excludes the ``locked`` safety block — this is a backup, not a
    config dump, and it should not carry a snapshot of the deployment's safety
    posture into a file that gets emailed around.
    """
    router = APIRouter()

    @router.get("/api/export")
    async def export_bundle() -> Response:
        sessions = store.list_sessions()
        bundle = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": 1,
            "sessions": sessions,
            "messages": [
                {**message, "session_id": session["id"]}
                for session in sessions
                for message in store.messages_for_session(session["id"])
            ],
            "memories": memory_store.list(),
            "preferences": {
                "values": preferences.effective(settings),
                "overridden": preferences.overridden(),
            },
        }
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return Response(
            content=json.dumps(bundle, indent=2, default=str),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="violet-export-{stamp}.json"'
            },
        )

    return router
```

- [ ] **Step 4: Wire into main.py**

Add the import beside the other route imports:

```python
from violet_assistant.routes.export import create_export_router
```

and register it next to the sessions router (after `main.py:230`):

```python
    app.include_router(
        create_export_router(store, memory_store, preferences, active_settings)
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest services/assistant-core/tests/test_export.py -q`
Expected: PASS — 3 tests.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add services/assistant-core/src/violet_assistant/routes/export.py services/assistant-core/src/violet_assistant/main.py services/assistant-core/tests/test_export.py
git commit -m "feat: export user data bundle"
```

---

# Phase C — Frontend foundation

> Phase C and D have no test runner. Each task's verification is `npm run build` plus the listed browser checks. To run the app: start the backend with `uvicorn violet_assistant.main:app --host 127.0.0.1 --port 8000` and the client with `npm run dev` from `apps/web-client` (Vite serves at `http://127.0.0.1:5173`).

## Task 8: API client for the new endpoints

**Files:**
- Modify: `apps/web-client/src/lib/api.ts`

**Interfaces:**
- Consumes: backend Tasks 4–7.
- Produces: `SettingsValues` type; `AppSettings` extended with `locked`; `resetSettings(target)`, `deleteSession(id)`, `deleteAllSessions()`, `exportUrl()`. Tasks 10–16 import these.

- [ ] **Step 1: Extend the settings types**

Replace the `AppSettings` block at `apps/web-client/src/lib/api.ts:203-220` with:

```typescript
export type SettingsValues = Record<string, string | number | boolean>;

export type AppSettings = {
  values: SettingsValues;
  defaults: SettingsValues;
  overridden: string[];
  locked: Record<string, string | number | boolean>;
};

export type SettingsGroup =
  | "general"
  | "appearance"
  | "model"
  | "behavior"
  | "voice"
  | "knowledge";

export async function fetchSettings(): Promise<AppSettings> {
  return requestJson<AppSettings>("/api/settings");
}

export async function patchSettings(
  changes: SettingsValues,
): Promise<AppSettings> {
  return requestJson<AppSettings>("/api/settings", {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}

export async function resetSettings(
  target: { group: SettingsGroup } | { keys: string[] },
): Promise<AppSettings> {
  return requestJson<AppSettings>("/api/settings/reset", {
    method: "POST",
    body: JSON.stringify(target),
  });
}
```

- [ ] **Step 2: Add the session and export functions**

Append to `apps/web-client/src/lib/api.ts`:

```typescript
export type DeleteReport = {
  deleted_sessions: number;
  deleted_messages: number;
  deleted_candidates: number;
  deleted_agent_runs: number;
};

export async function deleteSession(id: string): Promise<DeleteReport> {
  return requestJson<DeleteReport>(`/api/sessions/${id}`, { method: "DELETE" });
}

export async function deleteAllSessions(): Promise<DeleteReport> {
  return requestJson<DeleteReport>("/api/sessions", { method: "DELETE" });
}

/** Absolute URL for the export download. The browser handles the attachment
 *  response directly, so this is a link target rather than a fetch. */
export function exportUrl(): string {
  return `${apiBaseUrl}/api/export`;
}
```

- [ ] **Step 3: Verify the build**

Run: `cd apps/web-client && npm run build`
Expected: PASS. If `tsc` reports that `AppSettings.locked` is missing where the old type was constructed in tests or mocks, fix those call sites — the field is required.

- [ ] **Step 4: Commit**

```bash
git add apps/web-client/src/lib/api.ts
git commit -m "feat: api client for settings reset, session delete, export"
```

---

## Task 9: Theme tokens and flash-free application

**Files:**
- Create: `apps/web-client/src/lib/theme.ts`
- Modify: `apps/web-client/src/index.css`, `apps/web-client/index.html`

**Interfaces:**
- Consumes: `SettingsValues` (Task 8).
- Produces: `type Appearance = {theme, density, fontScale, accent}`; `applyAppearance(a)`, `appearanceFromSettings(values)`, `readCachedAppearance()`, `writeCachedAppearance(a)`, `watchSystemTheme(onChange)`. Tasks 12 and 16 call these.

- [ ] **Step 1: Add the dark, accent, and density CSS**

Append to `apps/web-client/src/index.css`, after the existing `@theme` block:

```css
/* ============================================================
   Dark variant. Overrides the @theme tokens, so every utility
   that goes through a token inverts with no per-component work.
   Note --color-steel-dark flips from near-black to near-white:
   it is the primary ink token, and its name describes its
   light-mode value, not its role.
   ============================================================ */
[data-theme="dark"] {
  --color-navy-950: #14101c;
  --color-navy-900: #1c1626;
  --color-navy-800: #241d31;
  --color-navy-700: #3a2f4d;
  --color-steel: #b9a9d1;
  --color-steel-light: #8d7da8;
  --color-steel-ice: #241d31;
  --color-steel-dark: #f2ecfa;
  --color-steel-highlight: #a855f7;
}

/* Semantic status colors, so components stop reaching for raw
   Tailwind palette entries that cannot follow the theme. */
:root {
  --color-success: #059669;
  --color-warning: #d97706;
}
[data-theme="dark"] {
  --color-success: #34d399;
  --color-warning: #fbbf24;
}

/* Accent — one hue per theme, each checked for >=4.5:1 against its
   surface because the accent is used for text, not only for fills. */
[data-accent="indigo"] { --color-steel-highlight: #4f46e5; }
[data-accent="teal"]   { --color-steel-highlight: #0d9488; }
[data-accent="amber"]  { --color-steel-highlight: #b45309; }
[data-accent="rose"]   { --color-steel-highlight: #be123c; }

[data-theme="dark"][data-accent="indigo"] { --color-steel-highlight: #818cf8; }
[data-theme="dark"][data-accent="teal"]   { --color-steel-highlight: #2dd4bf; }
[data-theme="dark"][data-accent="amber"]  { --color-steel-highlight: #fbbf24; }
[data-theme="dark"][data-accent="rose"]   { --color-steel-highlight: #fb7185; }

/* Font scale multiplies the root size, so every rem-based utility
   scales at once. */
html {
  font-size: calc(16px * var(--font-scale, 1));
}

/* Density touches vertical rhythm only. A density switch that also
   changed horizontal padding and type sizes would be a second theme
   in disguise, with a much larger visual-regression surface. */
:root { --row-pad: 0.75rem; }
[data-density="compact"] { --row-pad: 0.5rem; }
```

- [ ] **Step 2: Create the theme module**

Create `apps/web-client/src/lib/theme.ts`:

```typescript
import type { SettingsValues } from "./api";

export type ThemeChoice = "light" | "dark" | "system";
export type DensityChoice = "cozy" | "compact";
export type AccentChoice = "violet" | "indigo" | "teal" | "amber" | "rose";

export type Appearance = {
  theme: ThemeChoice;
  density: DensityChoice;
  fontScale: number;
  accent: AccentChoice;
};

export const DEFAULT_APPEARANCE: Appearance = {
  theme: "system",
  density: "cozy",
  fontScale: 1,
  accent: "violet",
};

const CACHE_KEY = "violet.appearance";

function prefersDark(): boolean {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

/** Stamp the appearance onto <html>. Everything else is CSS. */
export function applyAppearance(appearance: Appearance): void {
  const root = document.documentElement;
  const resolved =
    appearance.theme === "system"
      ? prefersDark()
        ? "dark"
        : "light"
      : appearance.theme;
  root.dataset.theme = resolved;
  root.dataset.density = appearance.density;
  root.dataset.accent = appearance.accent;
  root.style.setProperty("--font-scale", String(appearance.fontScale));
}

export function appearanceFromSettings(values: SettingsValues): Appearance {
  return {
    theme: (values.theme as ThemeChoice) ?? DEFAULT_APPEARANCE.theme,
    density: (values.ui_density as DensityChoice) ?? DEFAULT_APPEARANCE.density,
    fontScale: Number(values.font_scale ?? DEFAULT_APPEARANCE.fontScale),
    accent: (values.accent as AccentChoice) ?? DEFAULT_APPEARANCE.accent,
  };
}

export function readCachedAppearance(): Appearance {
  try {
    const raw = window.localStorage.getItem(CACHE_KEY);
    if (!raw) return DEFAULT_APPEARANCE;
    return { ...DEFAULT_APPEARANCE, ...(JSON.parse(raw) as Partial<Appearance>) };
  } catch {
    return DEFAULT_APPEARANCE;
  }
}

/** The cache is a paint hint only — the server value always overwrites it. */
export function writeCachedAppearance(appearance: Appearance): void {
  try {
    window.localStorage.setItem(CACHE_KEY, JSON.stringify(appearance));
  } catch {
    /* private browsing or a full quota — the server value still applies */
  }
}

/** Track OS theme changes while theme === "system". Returns an unsubscribe. */
export function watchSystemTheme(onChange: () => void): () => void {
  const query = window.matchMedia?.("(prefers-color-scheme: dark)");
  if (!query) return () => {};
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}
```

- [ ] **Step 3: Add the pre-paint script**

Replace the `<head>` of `apps/web-client/index.html`:

```html
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Violet AI</title>
    <script>
      // Stamp the cached appearance before the bundle loads, so a dark-theme
      // user does not see a flash of light while /api/settings is in flight.
      // The server value overwrites this as soon as it arrives.
      (function () {
        try {
          var a = JSON.parse(localStorage.getItem("violet.appearance") || "{}");
          var t = a.theme || "system";
          var dark =
            t === "dark" ||
            (t === "system" &&
              window.matchMedia("(prefers-color-scheme: dark)").matches);
          var root = document.documentElement;
          root.dataset.theme = dark ? "dark" : "light";
          root.dataset.density = a.density || "cozy";
          root.dataset.accent = a.accent || "violet";
          root.style.setProperty("--font-scale", String(a.fontScale || 1));
        } catch (e) {
          /* first visit, or storage blocked — defaults apply */
        }
      })();
    </script>
  </head>
```

- [ ] **Step 4: Verify the build**

Run: `cd apps/web-client && npm run build`
Expected: PASS.

- [ ] **Step 5: Browser check**

Start the app. In DevTools console run:

```js
document.documentElement.dataset.theme = "dark"
```

Expected: the whole UI inverts — background, sidebar, cards, and body text. Note every element that stays light; those are the hardcoded colors Task 17 sweeps. Do not fix them here.

Then run `document.documentElement.style.setProperty("--font-scale", "1.25")` and confirm all text grows proportionally.

- [ ] **Step 6: Commit**

```bash
git add apps/web-client/src/lib/theme.ts apps/web-client/src/index.css apps/web-client/index.html
git commit -m "feat: dark theme tokens, accent, density, font scale"
```

---

## Task 10: Settings shell, nav, and shared controls

**Files:**
- Create: `apps/web-client/src/components/settings/SettingsShell.tsx`, `SettingsNav.tsx`, `useDebouncedPatch.ts`, `controls/ToggleRow.tsx`, `controls/SegmentedRow.tsx`, `controls/SliderRow.tsx`, `controls/TextRow.tsx`, `controls/SectionHeader.tsx`

**Interfaces:**
- Consumes: `AppSettings`, `SettingsValues`, `SettingsGroup`, `resetSettings` (Task 8).
- Produces: `PanelProps` type and the `SettingsShell` component (both from `settings/SettingsShell.tsx`); `NavItem` and `SettingsNav`; the five control components. Tasks 11–15 build panels against these exact signatures.

The shell is named `SettingsShell`, not `SettingsModal` — Task 11 adds `SettingsPanel.tsx` for the assembled modal, and two files a letter apart would be a standing source of wrong imports. The **old** `components/SettingsModal.tsx` (one directory up) stays in place and in use until Task 11 swaps it out, so the app keeps building.

- [ ] **Step 1: Create the debounce hook**

Create `apps/web-client/src/components/settings/useDebouncedPatch.ts`:

```typescript
import { useCallback, useEffect, useRef } from "react";
import type { SettingsValues } from "../../lib/api";

/**
 * Coalesce rapid preference edits into one PATCH.
 *
 * A range input fires onChange on every step of a drag; patching directly meant
 * one HTTP request and one JSON file write per 0.1 of temperature. Controls hold
 * their own local value for responsiveness and call this to persist.
 */
export function useDebouncedPatch(
  patch: (changes: SettingsValues) => void,
  delayMs = 300,
): { push: (changes: SettingsValues) => void; flush: () => void } {
  const pending = useRef<SettingsValues>({});
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flush = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    if (Object.keys(pending.current).length === 0) return;
    const changes = pending.current;
    pending.current = {};
    patch(changes);
  }, [patch]);

  const push = useCallback(
    (changes: SettingsValues) => {
      pending.current = { ...pending.current, ...changes };
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(flush, delayMs);
    },
    [delayMs, flush],
  );

  // Flush on unmount so a value typed and immediately dismissed is not lost.
  useEffect(() => flush, [flush]);

  return { push, flush };
}
```

- [ ] **Step 2: Create the controls**

Create `apps/web-client/src/components/settings/controls/ToggleRow.tsx`:

```typescript
import type { ReactNode } from "react";

export function ToggleRow({
  label,
  hint,
  on,
  onToggle,
  icon,
}: {
  label: string;
  hint?: string;
  on: boolean;
  onToggle: () => void;
  icon?: ReactNode;
}) {
  return (
    <div className="flex items-start gap-2 text-xs text-steel-dark">
      {icon}
      <div className="min-w-0">
        <span className="font-medium">{label}</span>
        {hint && <p className="text-[11px] text-steel/60 mt-0.5">{hint}</p>}
      </div>
      <button
        type="button"
        onClick={onToggle}
        role="switch"
        aria-checked={on}
        aria-label={label}
        className={`ml-auto shrink-0 w-9 h-5 rounded-full transition relative ${
          on ? "bg-steel-highlight" : "bg-navy-700/30"
        }`}
      >
        <span
          className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${
            on ? "left-4" : "left-0.5"
          }`}
        />
      </button>
    </div>
  );
}
```

Create `apps/web-client/src/components/settings/controls/SegmentedRow.tsx`:

```typescript
export function SegmentedRow<T extends string>({
  label,
  value,
  options,
  onSelect,
}: {
  label: string;
  value: T;
  options: readonly { value: T; label: string }[];
  onSelect: (value: T) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium text-steel-dark">{label}</span>
      <div
        role="radiogroup"
        aria-label={label}
        className="ml-auto inline-flex rounded-full bg-steel-ice border border-navy-700/20 p-0.5"
      >
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={option.value === value}
            onClick={() => onSelect(option.value)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition ${
              option.value === value
                ? "bg-steel-dark text-white"
                : "text-steel hover:text-steel-dark"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
```

Create `apps/web-client/src/components/settings/controls/SliderRow.tsx`:

```typescript
import { useEffect, useState } from "react";

export function SliderRow({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format?: (value: number) => string;
  onChange: (value: number) => void;
}) {
  // Local state keeps the thumb responsive; the parent debounces the write.
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);

  return (
    <div>
      <div className="flex items-center justify-between text-xs text-steel-dark mb-1">
        <span className="font-medium">{label}</span>
        <span className="font-mono text-steel">
          {format ? format(local) : local.toFixed(1)}
        </span>
      </div>
      <input
        type="range"
        aria-label={label}
        min={min}
        max={max}
        step={step}
        value={local}
        onChange={(event) => {
          const next = Number(event.target.value);
          setLocal(next);
          onChange(next);
        }}
        className="w-full accent-steel-highlight"
      />
    </div>
  );
}
```

Create `apps/web-client/src/components/settings/controls/TextRow.tsx`:

```typescript
import { useEffect, useState } from "react";

export function TextRow({
  label,
  value,
  placeholder,
  hint,
  onChange,
}: {
  label: string;
  value: string;
  placeholder?: string;
  hint?: string;
  onChange: (value: string) => void;
}) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);

  return (
    <div>
      <label className="block text-xs font-medium text-steel-dark mb-1">
        {label}
      </label>
      <input
        value={local}
        placeholder={placeholder}
        onChange={(event) => {
          setLocal(event.target.value);
          onChange(event.target.value);
        }}
        className="w-full text-xs font-mono bg-white border border-navy-700/20 rounded-lg px-2.5 py-1.5 text-steel-dark focus:outline-none focus:ring-1 focus:ring-steel-highlight/30"
      />
      {hint && <p className="text-[11px] text-steel/60 mt-1">{hint}</p>}
    </div>
  );
}
```

Create `apps/web-client/src/components/settings/controls/SectionHeader.tsx`:

```typescript
import { RotateCcw } from "lucide-react";

export function SectionHeader({
  title,
  description,
  modified,
  onReset,
}: {
  title: string;
  description?: string;
  modified: boolean;
  onReset?: () => void;
}) {
  return (
    <div className="flex items-start gap-2 pb-4 mb-5 border-b border-navy-700/20">
      <div className="min-w-0">
        <h3 className="text-base font-semibold text-steel-dark flex items-center gap-2">
          {title}
          {modified && (
            <span
              title="Changed from defaults"
              aria-label="Changed from defaults"
              className="w-1.5 h-1.5 rounded-full bg-steel-highlight"
            />
          )}
        </h3>
        {description && (
          <p className="text-[11px] text-steel/70 mt-1">{description}</p>
        )}
      </div>
      {onReset && (
        <button
          type="button"
          onClick={onReset}
          disabled={!modified}
          className="ml-auto shrink-0 flex items-center gap-1 text-[11px] text-steel hover:text-steel-highlight disabled:opacity-30 disabled:hover:text-steel"
        >
          <RotateCcw size={12} />
          Reset section
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create the nav**

Create `apps/web-client/src/components/settings/SettingsNav.tsx`:

```typescript
import type { ReactNode } from "react";

export type NavItem = {
  id: string;
  label: string;
  icon: ReactNode;
  devOnly?: boolean;
};

export function SettingsNav({
  items,
  active,
  onSelect,
  devMode,
}: {
  items: NavItem[];
  active: string;
  onSelect: (id: string) => void;
  devMode: boolean;
}) {
  const visible = items.filter((item) => devMode || !item.devOnly);
  const firstDevIndex = visible.findIndex((item) => item.devOnly);

  return (
    <nav
      role="tablist"
      aria-orientation="vertical"
      aria-label="Settings sections"
      className="w-44 shrink-0 border-r border-navy-700/20 p-3 space-y-0.5 overflow-y-auto custom-scrollbar"
      onKeyDown={(event) => {
        if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
        event.preventDefault();
        const index = visible.findIndex((item) => item.id === active);
        const delta = event.key === "ArrowDown" ? 1 : -1;
        const next = (index + delta + visible.length) % visible.length;
        onSelect(visible[next].id);
      }}
    >
      {visible.map((item, index) => (
        <div key={item.id}>
          {index === firstDevIndex && firstDevIndex > 0 && (
            <div className="flex items-center gap-2 px-2 pt-3 pb-1.5">
              <span className="text-[10px] uppercase tracking-wider text-steel/50">
                dev
              </span>
              <span className="flex-1 h-px bg-navy-700/20" />
            </div>
          )}
          <button
            type="button"
            role="tab"
            aria-selected={item.id === active}
            tabIndex={item.id === active ? 0 : -1}
            onClick={() => onSelect(item.id)}
            className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs font-medium transition text-left ${
              item.id === active
                ? "bg-steel-highlight/10 text-steel-highlight"
                : "text-steel hover:bg-steel-ice hover:text-steel-dark"
            }`}
          >
            {item.icon}
            {item.label}
          </button>
        </div>
      ))}
    </nav>
  );
}
```

- [ ] **Step 4: Create the shell**

Create `apps/web-client/src/components/settings/SettingsShell.tsx`. This task ships the shell only; Task 11 assembles it with real panels.

```typescript
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";
import type { SettingsValues } from "../../lib/api";

export type PanelProps = {
  values: SettingsValues;
  overridden: string[];
  patch: (changes: SettingsValues) => void;
  devMode: boolean;
};

export function SettingsShell({
  open,
  onClose,
  title,
  nav,
  children,
  error,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  nav: ReactNode;
  children: ReactNode;
  error: string | null;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const returnFocusTo = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    returnFocusTo.current = document.activeElement as HTMLElement | null;
    const node = panelRef.current;
    node?.querySelector<HTMLElement>("[role='tab'][aria-selected='true']")?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !node) return;
      const focusable = node.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      returnFocusTo.current?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-steel-dark/30 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        className="bg-navy-800 border border-navy-700/20 rounded-[1.5rem] w-full max-w-4xl h-[min(85vh,42rem)] shadow-2xl relative flex flex-col overflow-hidden"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-center gap-3 px-6 py-4 border-b border-navy-700/20 shrink-0">
          <h2 id="settings-title" className="text-lg font-semibold text-steel-dark">
            {title}
          </h2>
          <button
            onClick={onClose}
            aria-label="Close settings"
            className="ml-auto text-steel hover:text-steel-dark"
          >
            <X size={18} />
          </button>
        </header>

        {error && (
          <p
            role="alert"
            className="px-6 py-2 text-xs text-[color:var(--color-warning)] bg-[color:var(--color-warning)]/10 border-b border-navy-700/20 shrink-0"
          >
            {error}
          </p>
        )}

        <div className="flex flex-1 min-h-0">
          {nav}
          <div className="flex-1 overflow-y-auto custom-scrollbar p-6">{children}</div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Verify the build**

Run: `cd apps/web-client && npm run build`
Expected: PASS. Nothing imports these yet, so the app is unchanged.

- [ ] **Step 6: Commit**

```bash
git add apps/web-client/src/components/settings/
git commit -m "feat: settings shell, nav rail, and shared controls"
```

---

# Phase D — Panels

## Task 11: Extract existing panels and swap the modal

**Files:**
- Create: `apps/web-client/src/components/settings/panels/GeneralPanel.tsx`, `BehaviorPanel.tsx`, `KnowledgePanel.tsx`, `SkillsPanel.tsx`, `AgentsPanel.tsx`, `ModelPanel.tsx`
- Create: `apps/web-client/src/components/settings/SettingsPanel.tsx` (the assembled modal)
- Modify: `apps/web-client/src/App.tsx`
- Delete: `apps/web-client/src/components/SettingsModal.tsx`

**Interfaces:**
- Consumes: `SettingsShell`, `PanelProps`, `SettingsNav`, controls (Task 10).
- Produces: `SettingsPanel` with the same props the old `SettingsModal` took, plus `onDeleteAllSessions`. Task 16 keeps this contract.

**Behavior must not change in this task.** Move each existing section into a panel verbatim — same controls, same `devMode` guards, same handlers. New behavior lands in Tasks 12–16. Keeping this task behavior-neutral is what makes a later regression bisectable.

- [ ] **Step 1: Extract the panels**

Create one file per panel. Each takes `PanelProps` plus whatever extras it needs, and moves the corresponding JSX out of the old `components/SettingsModal.tsx`:

- `GeneralPanel.tsx` — the Mode segmented control (lines 130–149 of the old file) and the Persona grid (207–226). Extra props: `personalities`, `personalityId`, `onSelectPersonality`.
- `ModelPanel.tsx` — the AI-engine provider list (151–178) and the cascade routing readout (180–205). Extra props: `providers`, `selectedProvider`, `onSelectProvider`, `router`. Temperature moves here too (277–295) — it belongs with the model, not with behavior. **This is the one placement change in this task; note it in the commit message.**
- `BehaviorPanel.tsx` — web search toggle + model input, canvas, memory approval (297–326).
- `SkillsPanel.tsx` — the skills list and Skill Lab button (331–363). Extra props: `skills`, `onOpenSkillLab`.
- `AgentsPanel.tsx` — the delegation picker (228–269). Extra props: `agents`, `selectedAgent`, `onSelectAgent`.
- `KnowledgePanel.tsx` — the whole knowledge block (365–470). Extra props: `knowledge`, `onReindex`, `onConnectGDrive`, `onDisconnectGDrive`.

Each panel starts with a `SectionHeader`. Compute `modified` from `overridden` and the group's keys, for example in `BehaviorPanel`:

```typescript
const BEHAVIOR_KEYS = [
  "web_search_enabled",
  "web_search_model",
  "canvas_enabled",
  "memory_require_approval",
  "memory_auto_save",
];

const modified = BEHAVIOR_KEYS.some((key) => overridden.includes(key));
```

The old Palette section (472–489) is **deleted**, not moved — Task 12's Appearance panel replaces it with controls that work.

- [ ] **Step 2: Assemble the modal**

Create `apps/web-client/src/components/settings/SettingsPanel.tsx` wiring `SettingsShell` + `SettingsNav` + a panel switch. Nav items:

```typescript
import {
  Bot, Database, Globe, Layers, Mic, Palette, Settings2, Sparkles, Shield,
} from "lucide-react";

const NAV: NavItem[] = [
  { id: "general", label: "General", icon: <Settings2 size={14} /> },
  { id: "appearance", label: "Appearance", icon: <Palette size={14} /> },
  { id: "behavior", label: "Behavior", icon: <Globe size={14} /> },
  { id: "voice", label: "Voice", icon: <Mic size={14} /> },
  { id: "knowledge", label: "Knowledge", icon: <Database size={14} /> },
  { id: "skills", label: "Skills", icon: <Sparkles size={14} /> },
  { id: "data", label: "Data & privacy", icon: <Shield size={14} /> },
  { id: "model", label: "Model", icon: <Layers size={14} />, devOnly: true },
  { id: "agents", label: "Agents", icon: <Bot size={14} />, devOnly: true },
];
```

The `appearance`, `voice`, and `data` entries render a one-line "Coming in the next task" `<p>` for now — Tasks 12, 14, and 15 replace them. Keeping the nav complete from the start means the shell is not rewritten three more times.

Wire the reset handler once, in `SettingsPanel`:

```typescript
async function handleReset(group: SettingsGroup) {
  try {
    setError(null);
    setAppSettings(await resetSettings({ group }));
  } catch (err) {
    setError(err instanceof Error ? err.message : "Reset failed");
  }
}
```

- [ ] **Step 3: Swap it into App.tsx**

In `apps/web-client/src/App.tsx`, change the import at line 57 from `./components/SettingsModal` to `./components/settings/SettingsPanel`, rename the element at line 698 to `<SettingsPanel .../>`, and keep every existing prop. Then delete `apps/web-client/src/components/SettingsModal.tsx`.

- [ ] **Step 4: Verify the build**

Run: `cd apps/web-client && npm run build`
Expected: PASS. A `tsc` error naming a prop that no panel consumes means something was dropped in extraction — find it before continuing.

- [ ] **Step 5: Browser check**

Open Settings and walk every nav entry. Confirm, against the pre-change behavior:

- Mode toggle still switches user/developer, and Model + Agents appear in the rail only in developer mode.
- Persona selection still changes the assistant name in the header.
- Web search, canvas, and memory-approval toggles still flip.
- Knowledge shows the same counts, and Reindex still runs.
- Skills lists the same entries; Skill Lab still opens.
- Escape closes the modal; focus returns to the settings button.

- [ ] **Step 6: Commit**

```bash
git add apps/web-client/src/components/settings/ apps/web-client/src/App.tsx
git rm apps/web-client/src/components/SettingsModal.tsx
git commit -m "refactor: split settings modal into per-group panels

Behavior-neutral except that temperature moves from Behavior to Model,
and the decorative Palette section is dropped ahead of the real
Appearance panel."
```

---

## Task 12: Appearance panel

**Files:**
- Create: `apps/web-client/src/components/settings/panels/AppearancePanel.tsx`
- Modify: `apps/web-client/src/components/settings/SettingsPanel.tsx`, `apps/web-client/src/App.tsx`

**Interfaces:**
- Consumes: `PanelProps` (Task 10), `applyAppearance` / `appearanceFromSettings` / `writeCachedAppearance` / `watchSystemTheme` (Task 9), backend keys from Task 2.
- Produces: `AppearancePanel` rendering theme, density, font scale, and accent.

- [ ] **Step 1: Create the panel**

Create `apps/web-client/src/components/settings/panels/AppearancePanel.tsx`:

```typescript
import type { PanelProps } from "../SettingsShell";
import { SectionHeader } from "../controls/SectionHeader";
import { SegmentedRow } from "../controls/SegmentedRow";
import { SliderRow } from "../controls/SliderRow";
import type { AccentChoice } from "../../../lib/theme";

const APPEARANCE_KEYS = ["theme", "ui_density", "font_scale", "accent"];

const ACCENTS: { value: AccentChoice; label: string; swatch: string }[] = [
  { value: "violet", label: "Violet", swatch: "#7b2cbf" },
  { value: "indigo", label: "Indigo", swatch: "#4f46e5" },
  { value: "teal", label: "Teal", swatch: "#0d9488" },
  { value: "amber", label: "Amber", swatch: "#b45309" },
  { value: "rose", label: "Rose", swatch: "#be123c" },
];

export function AppearancePanel({
  values,
  overridden,
  patch,
  onReset,
}: PanelProps & { onReset: () => void }) {
  const accent = (values.accent as AccentChoice) ?? "violet";

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Appearance"
        description="Applies immediately and follows you to any browser signed in to this assistant."
        modified={APPEARANCE_KEYS.some((key) => overridden.includes(key))}
        onReset={onReset}
      />

      <SegmentedRow
        label="Theme"
        value={(values.theme as string) ?? "system"}
        options={[
          { value: "light", label: "Light" },
          { value: "dark", label: "Dark" },
          { value: "system", label: "System" },
        ]}
        onSelect={(theme) => patch({ theme })}
      />

      <SegmentedRow
        label="Density"
        value={(values.ui_density as string) ?? "cozy"}
        options={[
          { value: "cozy", label: "Cozy" },
          { value: "compact", label: "Compact" },
        ]}
        onSelect={(ui_density) => patch({ ui_density })}
      />

      <SliderRow
        label="Font size"
        value={Number(values.font_scale ?? 1)}
        min={0.875}
        max={1.25}
        step={0.025}
        format={(value) => `${Math.round(value * 16)}px`}
        onChange={(font_scale) => patch({ font_scale })}
      />

      <div>
        <span className="block text-xs font-medium text-steel-dark mb-2">Accent</span>
        <div className="flex items-center gap-2">
          {ACCENTS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => patch({ accent: option.value })}
              aria-label={option.label}
              aria-pressed={option.value === accent}
              title={option.label}
              className={`w-7 h-7 rounded-full border-2 transition ${
                option.value === accent
                  ? "border-steel-dark scale-110"
                  : "border-transparent hover:scale-105"
              }`}
              style={{ backgroundColor: option.swatch }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Apply appearance from App.tsx**

In `App.tsx`, add the imports and an effect that applies appearance whenever settings change. Place it after the existing settings state declarations:

```typescript
import {
  appearanceFromSettings,
  applyAppearance,
  watchSystemTheme,
  writeCachedAppearance,
} from "./lib/theme";

// ...

useEffect(() => {
  if (!appSettings) return;
  const appearance = appearanceFromSettings(appSettings.values);
  applyAppearance(appearance);
  writeCachedAppearance(appearance);
  if (appearance.theme !== "system") return;
  // Follow OS changes while the app is open.
  return watchSystemTheme(() => applyAppearance(appearance));
}, [appSettings]);
```

- [ ] **Step 3: Wire the panel**

In `SettingsPanel.tsx`, replace the `appearance` placeholder with `<AppearancePanel ... onReset={() => handleReset("appearance")} />`.

- [ ] **Step 4: Verify the build**

Run: `cd apps/web-client && npm run build`
Expected: PASS.

- [ ] **Step 5: Browser check**

- Switch Theme to Dark. The UI inverts immediately, with no reload.
- Reload. It stays dark, and there is no flash of light before the app paints — watch the very first frame; if you see white, the `index.html` script is not running or the cache is not being written.
- Switch to System, change the OS theme, and confirm the app follows without a reload.
- Drag Font size; text scales. In DevTools Network, confirm the drag produced **one** PATCH to `/api/settings`, not one per step.
- Click each accent; buttons, links, and the active nav tab change hue.
- Click "Reset section"; all four return to defaults and the modified dot disappears.

- [ ] **Step 6: Commit**

```bash
git add apps/web-client/src/components/settings/panels/AppearancePanel.tsx apps/web-client/src/components/settings/SettingsPanel.tsx apps/web-client/src/App.tsx
git commit -m "feat: appearance settings panel"
```

---

## Task 13: Model panel gains editable model ids

**Files:**
- Modify: `apps/web-client/src/components/settings/panels/ModelPanel.tsx`

**Interfaces:**
- Consumes: `TextRow` (Task 10), model keys from Task 3.
- Produces: no new exports; the existing `ModelPanel` gains five text inputs.

Task 11 moved the provider list, the read-only cascade readout, and temperature here. This task turns the readout into editable fields.

- [ ] **Step 1: Replace the cascade readout with inputs**

In `ModelPanel.tsx`, replace the read-only persona/technical display with `TextRow`s, and add the remaining three behind the existing `devMode` guard:

```typescript
const MODEL_KEYS = [
  "llm_model",
  "temperature",
  "persona_model",
  "technical_model",
  "artifact_model",
  "vision_model",
  "agent_default_model",
  "web_search_model",
];

// ... inside the component, after the provider list and temperature slider:

{router?.mode === "cascade" && (
  <div className="space-y-3 p-3 bg-steel-ice rounded-xl border border-navy-700/20">
    <p className="text-[11px] text-steel/70">
      Persona answers; heavy calculation and code are delegated to the technical
      layer on demand. Blank falls back to the server default.
    </p>
    <TextRow
      label="Persona model"
      value={String(values.persona_model ?? "")}
      placeholder={String(defaults.persona_model ?? "")}
      onChange={(persona_model) => patch({ persona_model })}
    />
    <TextRow
      label="Technical model"
      value={String(values.technical_model ?? "")}
      placeholder={String(defaults.technical_model ?? "")}
      onChange={(technical_model) => patch({ technical_model })}
    />
  </div>
)}

<TextRow
  label="Artifact model"
  value={String(values.artifact_model ?? "")}
  placeholder={String(defaults.artifact_model ?? "")}
  hint="Generates canvas artifacts."
  onChange={(artifact_model) => patch({ artifact_model })}
/>
<TextRow
  label="Vision model"
  value={String(values.vision_model ?? "")}
  placeholder={String(defaults.vision_model ?? "")}
  hint="Reads uploaded images and scanned PDFs."
  onChange={(vision_model) => patch({ vision_model })}
/>
<TextRow
  label="Default agent model"
  value={String(values.agent_default_model ?? "")}
  placeholder={String(defaults.agent_default_model ?? "")}
  hint="Used by agents that do not pin their own model."
  onChange={(agent_default_model) => patch({ agent_default_model })}
/>
```

`ModelPanel` needs `defaults` in addition to `PanelProps`; add `defaults: SettingsValues` to its props and pass `appSettings.defaults` from `SettingsPanel`.

- [ ] **Step 2: Verify the build**

Run: `cd apps/web-client && npm run build`
Expected: PASS.

- [ ] **Step 3: Browser check**

- Switch to developer mode; the Model tab appears.
- Type into "Artifact model". Confirm in Network that typing produces **one** PATCH after you stop, not one per keystroke.
- Clear the field entirely and confirm the placeholder shows the server default — and that the backend still resolves the default (Task 3's blank-override test covers the logic; here just confirm the UI does not send garbage).
- Reload; the typed value persists.

- [ ] **Step 4: Commit**

```bash
git add apps/web-client/src/components/settings/panels/ModelPanel.tsx apps/web-client/src/components/settings/SettingsPanel.tsx
git commit -m "feat: editable model ids in the model panel"
```

---

## Task 14: Voice panel and preference-driven speech

**Files:**
- Create: `apps/web-client/src/components/settings/panels/VoicePanel.tsx`
- Modify: `apps/web-client/src/lib/speech.ts`, `apps/web-client/src/App.tsx`, `SettingsPanel.tsx`

**Interfaces:**
- Consumes: voice keys from Task 2, controls from Task 10.
- Produces: `VoiceSettings` type in `speech.ts`; `createSpeechRecognizer` and `speakText` gain a settings parameter; `listVoices()`.

`speech.ts` currently hardcodes `lang = "id-ID"`, `rate = 1`, `pitch = 1` in two places.

- [ ] **Step 1: Make speech.ts configurable**

In `apps/web-client/src/lib/speech.ts`, add the type and voice listing:

```typescript
export type VoiceSettings = {
  lang: string;
  voiceName: string;
  rate: number;
  pitch: number;
};

export const DEFAULT_VOICE: VoiceSettings = {
  lang: "id-ID",
  voiceName: "",
  rate: 1,
  pitch: 1,
};

/** Browser voice lists are per-browser and per-OS, and populate asynchronously. */
export function listVoices(): SpeechSynthesisVoice[] {
  if (!canSpeak()) return [];
  return window.speechSynthesis.getVoices();
}

export function onVoicesChanged(callback: () => void): () => void {
  if (!canSpeak()) return () => {};
  window.speechSynthesis.addEventListener("voiceschanged", callback);
  return () =>
    window.speechSynthesis.removeEventListener("voiceschanged", callback);
}
```

Change `createSpeechRecognizer` to take settings — replace the hardcoded `recognition.lang = "id-ID";` with `recognition.lang = voice.lang;` and add `voice: VoiceSettings = DEFAULT_VOICE` as its fourth parameter.

Replace `speakText` entirely:

```typescript
export function speakText(
  text: string,
  voice: VoiceSettings = DEFAULT_VOICE,
  onEnd?: () => void,
): void {
  if (!canSpeak()) {
    onEnd?.();
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = voice.lang;
  utterance.rate = voice.rate;
  utterance.pitch = voice.pitch;
  if (voice.voiceName) {
    // A stored name may not exist in this browser; fall back silently.
    const match = listVoices().find((item) => item.name === voice.voiceName);
    if (match) utterance.voice = match;
  }
  utterance.onend = () => onEnd?.();
  utterance.onerror = () => onEnd?.();
  window.speechSynthesis.speak(utterance);
}
```

Update every existing `speakText(...)` and `createSpeechRecognizer(...)` call site in `App.tsx` and `VoiceOverlay.tsx` to pass the settings object built from `appSettings.values`. Run `grep -rn "speakText\|createSpeechRecognizer" apps/web-client/src` to find them all.

- [ ] **Step 2: Create the panel**

Create `apps/web-client/src/components/settings/panels/VoicePanel.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { PanelProps } from "../SettingsShell";
import { SectionHeader } from "../controls/SectionHeader";
import { SliderRow } from "../controls/SliderRow";
import { ToggleRow } from "../controls/ToggleRow";
import { canSpeak, listVoices, onVoicesChanged, speakText } from "../../../lib/speech";

const VOICE_KEYS = [
  "voice_lang", "voice_name", "voice_rate", "voice_pitch", "auto_speak",
];

export function VoicePanel({
  values,
  overridden,
  patch,
  onReset,
}: PanelProps & { onReset: () => void }) {
  const [voices, setVoices] = useState(listVoices());
  useEffect(() => onVoicesChanged(() => setVoices(listVoices())), []);

  const voiceName = String(values.voice_name ?? "");
  const missing = voiceName !== "" && !voices.some((v) => v.name === voiceName);

  const current = {
    lang: String(values.voice_lang ?? "id-ID"),
    voiceName,
    rate: Number(values.voice_rate ?? 1),
    pitch: Number(values.voice_pitch ?? 1),
  };

  if (!canSpeak()) {
    return (
      <div className="space-y-5">
        <SectionHeader title="Voice" modified={false} />
        <p className="text-xs text-steel/70">
          This browser does not support speech synthesis, so voice settings would
          have no effect. Try a Chromium-based browser.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Voice"
        description="Uses your browser's built-in speech engine. Available voices differ by browser and operating system."
        modified={VOICE_KEYS.some((key) => overridden.includes(key))}
        onReset={onReset}
      />

      <div>
        <label className="block text-xs font-medium text-steel-dark mb-1">
          Voice
        </label>
        <select
          value={voiceName}
          onChange={(event) => patch({ voice_name: event.target.value })}
          className="w-full text-xs bg-white border border-navy-700/20 rounded-lg px-2.5 py-1.5 text-steel-dark"
        >
          <option value="">Browser default</option>
          {voices.map((voice) => (
            <option key={voice.name} value={voice.name}>
              {voice.name} ({voice.lang})
            </option>
          ))}
        </select>
        {missing && (
          <p className="text-[11px] text-[color:var(--color-warning)] mt-1">
            “{voiceName}” is not available in this browser. The default voice is
            being used instead.
          </p>
        )}
      </div>

      <div>
        <label className="block text-xs font-medium text-steel-dark mb-1">
          Language
        </label>
        <input
          value={String(values.voice_lang ?? "")}
          onChange={(event) => patch({ voice_lang: event.target.value })}
          placeholder="id-ID"
          className="w-full text-xs font-mono bg-white border border-navy-700/20 rounded-lg px-2.5 py-1.5 text-steel-dark"
        />
        <p className="text-[11px] text-steel/60 mt-1">
          BCP-47 tag, e.g. <span className="font-mono">id-ID</span> or{" "}
          <span className="font-mono">en-US</span>. Also used for speech input.
        </p>
      </div>

      <SliderRow
        label="Rate"
        value={current.rate}
        min={0.5}
        max={2}
        step={0.1}
        onChange={(voice_rate) => patch({ voice_rate })}
      />
      <SliderRow
        label="Pitch"
        value={current.pitch}
        min={0}
        max={2}
        step={0.1}
        onChange={(voice_pitch) => patch({ voice_pitch })}
      />

      <ToggleRow
        label="Speak replies automatically"
        hint="Reads each assistant reply aloud as it arrives."
        on={values.auto_speak === true}
        onToggle={() => patch({ auto_speak: !(values.auto_speak === true) })}
      />

      <button
        type="button"
        onClick={() =>
          speakText("Halo, saya Violet. Ini contoh suara saya.", current)
        }
        className="w-full text-xs font-medium text-steel-highlight bg-steel-highlight/10 hover:bg-steel-highlight/15 border border-steel-highlight/30 rounded-lg py-2 transition"
      >
        Test voice
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Honor auto_speak in App.tsx**

In `App.tsx`, where an assistant reply is appended in `send()` (after `setMessages(...)` around line 256), add:

```typescript
if (appSettings?.values.auto_speak === true) {
  speakText(response.text, {
    lang: String(appSettings.values.voice_lang ?? "id-ID"),
    voiceName: String(appSettings.values.voice_name ?? ""),
    rate: Number(appSettings.values.voice_rate ?? 1),
    pitch: Number(appSettings.values.voice_pitch ?? 1),
  });
}
```

- [ ] **Step 4: Verify the build**

Run: `cd apps/web-client && npm run build`
Expected: PASS.

- [ ] **Step 5: Browser check**

- Open the Voice tab; the voice dropdown is populated (it may fill a beat late — that is the `voiceschanged` event).
- Click "Test voice"; audio plays.
- Change Rate to 2.0 and test again; it is audibly faster.
- Set a voice, reload, confirm it is still selected.
- Enable "Speak replies automatically", send a message, confirm the reply is spoken.

- [ ] **Step 6: Commit**

```bash
git add apps/web-client/src/components/settings/panels/VoicePanel.tsx apps/web-client/src/lib/speech.ts apps/web-client/src/App.tsx apps/web-client/src/components/settings/SettingsPanel.tsx apps/web-client/src/components/VoiceOverlay.tsx
git commit -m "feat: voice settings drive browser speech"
```

---

## Task 15: Data & privacy panel

**Files:**
- Create: `apps/web-client/src/components/settings/panels/DataPanel.tsx`
- Modify: `apps/web-client/src/components/settings/SettingsPanel.tsx`, `apps/web-client/src/App.tsx`

**Interfaces:**
- Consumes: `locked` (Task 5), `deleteAllSessions` / `exportUrl` (Task 8).
- Produces: `DataPanel`; `SettingsPanel` gains an `onDeleteAllSessions: () => Promise<void>` prop that `App.tsx` supplies.

`DataPanel` is the one panel that does **not** take `PanelProps`. It edits no preferences — it shows a read-only block and performs two actions — so `values` / `overridden` / `patch` would all be dead props. Give it only what it uses.

- [ ] **Step 1: Create the panel**

Create `apps/web-client/src/components/settings/panels/DataPanel.tsx`:

```typescript
import { useState } from "react";
import { Download, Lock } from "lucide-react";
import { exportUrl } from "../../../lib/api";
import { SectionHeader } from "../controls/SectionHeader";

const LOCKED_LABELS: Record<string, string> = {
  llm_provider: "LLM provider",
  agent_tools_enabled: "Agent tools",
  allow_shell_tools: "Shell tools",
  allow_email_tools: "Email tools",
  allow_file_delete: "File deletion",
  require_confirmation_for_risky_tools: "Confirm risky tools",
  tool_confirm_threshold: "Confirmation threshold",
  max_tool_iterations: "Max tool iterations",
};

function renderValue(value: string | number | boolean) {
  if (typeof value !== "boolean") return String(value);
  return value ? "on" : "off";
}

export function DataPanel({
  locked,
  onDeleteAllSessions,
}: {
  locked: Record<string, string | number | boolean>;
  onDeleteAllSessions: () => Promise<void>;
}) {
  const [confirmText, setConfirmText] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Data & privacy"
        description="Everything here is stored locally on this machine."
        modified={false}
      />

      <div>
        <h4 className="text-xs font-semibold text-steel uppercase tracking-wider mb-2">
          Backup
        </h4>
        <a
          href={exportUrl()}
          download
          className="flex items-center justify-center gap-2 w-full text-xs font-medium text-steel-highlight bg-steel-highlight/10 hover:bg-steel-highlight/15 border border-steel-highlight/30 rounded-lg py-2.5 transition"
        >
          <Download size={13} />
          Export all data as JSON
        </a>
        <p className="text-[11px] text-steel/60 mt-1.5">
          Sessions, messages, memories, and your preference overrides. Do this
          before clearing anything.
        </p>
      </div>

      <div>
        <h4 className="flex items-center gap-1.5 text-xs font-semibold text-steel uppercase tracking-wider mb-2">
          <Lock size={12} />
          Safety configuration
        </h4>
        <div className="p-3 bg-steel-ice rounded-xl border border-navy-700/20 space-y-1.5">
          {Object.entries(locked).map(([key, value]) => (
            <div key={key} className="flex items-center gap-2 text-[11px]">
              <span className="text-steel-dark">{LOCKED_LABELS[key] ?? key}</span>
              <span className="ml-auto font-mono text-steel">
                {renderValue(value)}
              </span>
            </div>
          ))}
          <p className="text-[11px] text-steel/60 pt-1.5 border-t border-navy-700/10">
            Read-only. These are set in <span className="font-mono">.env</span> and
            deliberately cannot be changed from the browser.
          </p>
        </div>
      </div>

      <div>
        <h4 className="text-xs font-semibold text-[color:var(--color-warning)] uppercase tracking-wider mb-2">
          Danger zone
        </h4>
        <div className="p-3 rounded-xl border border-[color:var(--color-warning)]/30 bg-[color:var(--color-warning)]/5 space-y-2">
          <p className="text-[11px] text-steel-dark">
            Deletes every session and message. Approved memories are kept. This
            cannot be undone.
          </p>
          <input
            value={confirmText}
            onChange={(event) => setConfirmText(event.target.value)}
            placeholder="Type delete to confirm"
            aria-label="Type delete to confirm"
            className="w-full text-xs bg-white border border-navy-700/20 rounded-lg px-2.5 py-1.5 text-steel-dark"
          />
          <button
            type="button"
            disabled={confirmText !== "delete" || busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onDeleteAllSessions();
                setConfirmText("");
              } finally {
                setBusy(false);
              }
            }}
            className="w-full text-xs font-semibold text-white bg-[color:var(--color-warning)] rounded-lg py-2 transition disabled:opacity-30"
          >
            {busy ? "Clearing…" : "Clear all sessions"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire the handler in App.tsx**

Add near the other handlers:

```typescript
async function handleDeleteAllSessions() {
  try {
    const report = await deleteAllSessions();
    await refreshSessions();
    setMessages([]);
    setSessionId(null);
    await refreshMemory();
    setStatus({
      tone: "ok",
      text: `Cleared ${report.deleted_sessions} sessions, ${report.deleted_messages} messages`,
    });
  } catch (error) {
    setStatus({
      tone: "error",
      text: error instanceof Error ? error.message : "Clear failed",
    });
  }
}
```

Import `deleteAllSessions` from `./lib/api` and pass `onDeleteAllSessions={handleDeleteAllSessions}` to `SettingsPanel`. `refreshMemory()` is called because clearing sessions removes orphaned memory candidates, and the drawer would otherwise still show them.

- [ ] **Step 3: Verify the build**

Run: `cd apps/web-client && npm run build`
Expected: PASS.

- [ ] **Step 4: Browser check**

- Open Data & privacy. The safety list shows all eight flags with sensible labels; nothing there is editable and no key, URL, or path appears.
- Click Export; a `violet-export-*.json` file downloads. Open it and confirm it contains your sessions and messages, and contains no `api_key` or `base_url`.
- Type `delet` — the clear button stays disabled. Type `delete` — it enables.
- With at least two sessions present, click it. The sidebar empties, the chat resets, and the status bar reports the counts.

- [ ] **Step 5: Commit**

```bash
git add apps/web-client/src/components/settings/panels/DataPanel.tsx apps/web-client/src/components/settings/SettingsPanel.tsx apps/web-client/src/App.tsx
git commit -m "feat: data and privacy panel with export and clear"
```

---

# Phase E — Integration

## Task 16: Persist persona and provider selections

**Files:**
- Modify: `apps/web-client/src/App.tsx`

**Interfaces:**
- Consumes: `default_personality` / `default_provider` keys (Task 1), `patchSettings` (Task 8).
- Produces: no new exports.

Today `personalityId` initializes to a hardcoded `"violet.default"` (`App.tsx:83`) and `setSelectedProvider(providerResponse.active)` overwrites any stored choice on load (`App.tsx:193`), so both reset on every reload despite the keys existing.

- [ ] **Step 1: Initialize from settings**

Replace the settings bootstrap at `App.tsx:204-206` so it seeds the selections:

```typescript
fetchSettings()
  .then((settings) => {
    setAppSettings(settings);
    const persona = String(settings.values.default_personality ?? "");
    if (persona) setPersonalityId(persona);
    const provider = String(settings.values.default_provider ?? "");
    if (provider) setSelectedProvider(provider);
  })
  .catch(() => setAppSettings(null));
```

The personalities bootstrap already falls back when a stored id no longer exists (`App.tsx:186-191`) — a personality removed from `configs/personality/` must not leave the app pointing at a missing profile. Verify that guard still runs after this change; it must compare against whatever `setPersonalityId` ended up with, so leave it in place and confirm ordering by testing the removal case in Step 4.

Remove the unconditional `setSelectedProvider(providerResponse.active)` at line 193 — the server's active provider is now only the *fallback*, applied by `default_provider`'s default, not an override that stomps the user's choice on every load.

- [ ] **Step 2: Persist on selection**

Change the handlers passed to `SettingsPanel`:

```typescript
onSelectPersonality={(id) => {
  setPersonalityId(id);
  handlePatchSettings({ default_personality: id });
}}
onSelectProvider={(id) => {
  setSelectedProvider(id);
  handlePatchSettings({ default_provider: id });
}}
```

`selectedAgent` stays session-local and is deliberately **not** persisted — agent delegation is a per-task choice, and silently resuming a delegation days later would be surprising.

- [ ] **Step 3: Verify the build**

Run: `cd apps/web-client && npm run build`
Expected: PASS.

- [ ] **Step 4: Browser check**

- Select a non-default persona. Reload. It is still selected, and the assistant name in the header matches.
- Select a different provider. Reload. Still selected.
- Rename or move a file in `configs/personality/` so the stored id no longer resolves, restart the backend, reload. The app falls back to the first available personality rather than showing an empty or broken selection. Restore the file afterward.
- Select an agent, reload, and confirm the agent selection is cleared — that is intended.

- [ ] **Step 5: Commit**

```bash
git add apps/web-client/src/App.tsx
git commit -m "fix: persist persona and provider selections across reloads"
```

---

## Task 17: Hardcoded color sweep

**Files:**
- Modify: any file under `apps/web-client/src/components/` that the sweep finds

**Interfaces:** none — this is a correctness pass over Task 9's theme.

Token overrides only reach utilities that go through tokens. Anything using an arbitrary hex or a raw Tailwind palette color stays light-mode-colored in dark mode.

- [ ] **Step 1: Find the offenders**

Run from the repo root:

```bash
grep -rnE "\[#[0-9a-fA-F]{3,8}\]|text-(emerald|amber|red|green|blue|slate|gray|zinc)-[0-9]{3}|bg-(emerald|amber|red|green|blue|slate|gray|zinc)-[0-9]{3}" apps/web-client/src --include=*.tsx
```

Record the full list before changing anything — you will check it back to empty in Step 3.

- [ ] **Step 2: Convert each hit**

- Semantic status colors (`text-emerald-600` for connected, `text-amber-600` for warnings) become `text-[color:var(--color-success)]` and `text-[color:var(--color-warning)]`, which Task 9 defined for both themes.
- Arbitrary brand hexes become the nearest existing token — usually `text-steel-highlight` or `bg-steel-highlight`.
- If a hit is genuinely theme-independent (a fixed brand swatch in `AppearancePanel`'s accent picker, which must show its true color in both themes), leave it and add a short comment saying why. Do not convert those.

- [ ] **Step 3: Verify the sweep**

Re-run the grep from Step 1. Every remaining hit must be one you deliberately kept with a comment.

Run: `cd apps/web-client && npm run build`
Expected: PASS.

- [ ] **Step 4: Browser check in dark mode**

With Theme set to Dark, visit every surface and look for anything still light: the chat timeline (user and assistant bubbles, citations, tool trace, tool approval card), the sidebar and session list, the composer and attachment chip, the memory drawer, the canvas/artifact view, the skill palette and Skill Lab, the avatar panel, the help modal, and all nine settings panels. Fix anything that stands out and re-check.

- [ ] **Step 5: Commit**

```bash
git add apps/web-client/src/components/
git commit -m "fix: route hardcoded colors through theme tokens"
```

---

## Task 18: Full verification and log

**Files:**
- Create: `logs/settings-overhaul-implementation_2026-07-27_log.md`

**Interfaces:** none.

- [ ] **Step 1: Run the full backend suite**

Run: `python -m pytest -q`
Expected: all pass. Record the exact count — the log needs evidence, not an assertion.

- [ ] **Step 2: Run the frontend build**

Run: `cd apps/web-client && npm run build`
Expected: PASS with no TypeScript errors.

- [ ] **Step 3: End-to-end walkthrough**

With both services running, confirm in one pass:

1. Settings opens; all seven user-mode tabs render; Model and Agents appear only in developer mode.
2. Escape closes; focus returns to the trigger; arrow keys move between tabs.
3. Dark theme applies, survives reload with no flash, and every surface inverts.
4. Dragging temperature and font size each produce exactly one PATCH.
5. Persona and provider survive a reload.
6. Voice test speaks with the configured rate.
7. Export downloads a bundle containing your data and no secrets.
8. Clear-all requires typing `delete`, then empties the sidebar.
9. "Reset section" restores a section and clears its modified dot.
10. Stopping the backend and toggling a setting shows an error **inside** the modal, not behind it.

- [ ] **Step 4: Write the log**

Create `logs/settings-overhaul-implementation_2026-07-27_log.md` from `logs/_TEMPLATE.md`. Fill Verification with the actual pytest count and build result from Steps 1–2 and the walkthrough outcome from Step 3 — including anything that failed and what was done about it. Do not write "all passed" unless it did.

- [ ] **Step 5: Commit**

```bash
git add logs/settings-overhaul-implementation_2026-07-27_log.md
git commit -m "docs: implementation log for the settings overhaul"
```

---

## Spec coverage

| Spec section | Tasks |
|---|---|
| Part 1 — store structure, 25-key table, model-key wiring | 1, 2, 3 |
| Part 2 — reset, locked, session delete, export | 4, 5, 6, 7 |
| Part 3 — directory split, panel contract, group visibility, debounce, a11y, error feedback | 10, 11, 12–15 |
| Part 4 — dark tokens, accent, density, font scale, hardcoded sweep, first-paint flash | 9, 17 |
| Part 5 — persona/provider persistence, voice reads prefs, destructive gating | 16, 14, 15 |
| Security boundary | 5 (allowlist + no-secrets test), 7 (export exclusion), 15 (read-only UI) |
| Testing section | Every backend task; 18 for the end-to-end pass |
