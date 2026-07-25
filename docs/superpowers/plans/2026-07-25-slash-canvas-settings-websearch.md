# Slash Skills · Runtime Settings · Canvas · Web Search — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user explicitly invoke skills via `/`, edit behavior preferences at runtime, view artifacts in a dedicated canvas panel, and search/crawl the web.

**Architecture:** Backend (FastAPI `violet_assistant`) gains a `PreferencesStore` (JSON-backed, merged over the frozen `Settings`), an explicit-skill + web-search routing branch in `ChatOrchestrator`, and a stdlib-only URL fetch tool. Frontend (React + Vite `web-client`) gains a slash skill palette, an expanded settings modal, a canvas side panel that reuses extracted artifact renderers, and a web-search composer toggle.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, pytest (backend); React 18, TypeScript, Vite, Tailwind, lucide-react, Chart.js (frontend). No new runtime dependencies — web calls and URL fetch use stdlib `urllib`/`html.parser`.

## Global Constraints

- Python `>=3.11`; backend package root is `services/assistant-core/src/violet_assistant`.
- Run backend tests from `services/assistant-core` with `python -m pytest` (basetemp `.tmp/pytest`).
- No secrets in code or committed files; secrets stay in `.env`. Only behavior/UX preferences are runtime-editable.
- Do NOT make runtime-editable: API keys, base URLs, DB paths, or the `ALLOW_*` safety toggles.
- HTML artifacts keep the existing sandbox (`sandbox="allow-scripts"`, CSP `connect-src 'none'`).
- Every unit of work: add/adjust tests where applicable, then write a `logs/{update}_{YYYY-MM-DD}_log.md` entry (use `logs/_TEMPLATE.md`) BEFORE committing. Date is 2026-07-25.
- Frontend has no JS test harness; verify frontend tasks with `cd apps/web-client && npm run build` (typecheck + build) plus manual smoke.
- Add `temperature` default constant `0.2` where a default is needed.

---

### Task 1: Preferences store + settings API

**Files:**
- Create: `services/assistant-core/src/violet_assistant/preferences/__init__.py`
- Create: `services/assistant-core/src/violet_assistant/preferences/store.py`
- Create: `services/assistant-core/src/violet_assistant/routes/settings.py`
- Modify: `services/assistant-core/src/violet_assistant/config.py` (add `web_search_base_url`, `web_search_model`, `web_search_api_key`, `default_temperature`)
- Modify: `services/assistant-core/src/violet_assistant/main.py` (build store, include router)
- Test: `services/assistant-core/tests/test_preferences.py`

**Interfaces:**
- Produces: `PreferencesStore(path: Path)` with `.effective(settings: Settings) -> dict`, `.patch(changes: dict) -> dict`, `.overridden() -> list[str]`, `.defaults(settings) -> dict`.
- Produces routes `GET /api/settings`, `PATCH /api/settings` returning `{"values": dict, "defaults": dict, "overridden": list[str]}`.
- Consumes: `Settings` from config.

- [ ] **Step 1: Write the failing test**

```python
# services/assistant-core/tests/test_preferences.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from violet_assistant.config import load_settings
from violet_assistant.preferences.store import EDITABLE_KEYS, PreferencesStore


@pytest.fixture()
def settings(tmp_path):
    return load_settings(tmp_path)


def test_defaults_when_no_file(tmp_path, settings):
    store = PreferencesStore(tmp_path / "preferences.json")
    values = store.effective(settings)
    assert set(values) == set(EDITABLE_KEYS)
    assert values["temperature"] == 0.2
    assert values["canvas_enabled"] is True
    assert store.overridden() == []


def test_patch_persists_and_merges(tmp_path, settings):
    path = tmp_path / "preferences.json"
    store = PreferencesStore(path)
    result = store.patch({"temperature": 0.9, "web_search_enabled": True})
    assert result["temperature"] == 0.9
    assert result["web_search_enabled"] is True
    # persisted to disk
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["temperature"] == 0.9
    # a fresh store reads the override back
    assert PreferencesStore(path).effective(settings)["temperature"] == 0.9
    assert set(PreferencesStore(path).overridden()) == {"temperature", "web_search_enabled"}


def test_patch_rejects_unknown_key(tmp_path):
    store = PreferencesStore(tmp_path / "preferences.json")
    with pytest.raises(ValueError):
        store.patch({"llm_api_key": "sk-nope"})


def test_patch_validates_temperature_range(tmp_path):
    store = PreferencesStore(tmp_path / "preferences.json")
    with pytest.raises(ValueError):
        store.patch({"temperature": 5.0})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/assistant-core && python -m pytest tests/test_preferences.py -v`
Expected: FAIL with `ModuleNotFoundError: violet_assistant.preferences`.

- [ ] **Step 3: Add config fields**

In `config.py`, add to the `Settings` dataclass (after the vision block, keep it frozen):

```python
    # Web search (Phase 4) — key reuses OpenRouter.
    web_search_base_url: str = "https://openrouter.ai/api/v1"
    web_search_model: str = "deepseek/deepseek-chat-v3.1"
    web_search_api_key: str | None = None
    default_temperature: float = 0.2
```

In `load_settings(...)`, add these to the `Settings(...)` construction:

```python
        web_search_base_url=os.getenv(
            "WEB_SEARCH_BASE_URL",
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        ),
        web_search_model=os.getenv(
            "WEB_SEARCH_MODEL",
            os.getenv("TECHNICAL_MODEL", "deepseek/deepseek-chat-v3.1"),
        ),
        web_search_api_key=os.getenv("WEB_SEARCH_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or None,
        default_temperature=float(os.getenv("DEFAULT_TEMPERATURE", "0.2")),
```

- [ ] **Step 4: Write the preferences store**

```python
# services/assistant-core/src/violet_assistant/preferences/__init__.py
```

```python
# services/assistant-core/src/violet_assistant/preferences/store.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from violet_assistant.config import Settings

# Editable keys map to (validator, default-from-settings). NO secrets here.
_BOOL = lambda v: isinstance(v, bool)  # noqa: E731


def _num(lo: float, hi: float) -> Callable[[Any], bool]:
    return lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi


def _str(v: Any) -> bool:
    return isinstance(v, str) and len(v) <= 200


EDITABLE_KEYS: dict[str, Callable[[Any], bool]] = {
    "llm_model": _str,
    "temperature": _num(0.0, 2.0),
    "memory_require_approval": _BOOL,
    "memory_auto_save": _BOOL,
    "web_search_enabled": _BOOL,
    "web_search_model": _str,
    "canvas_enabled": _BOOL,
    "default_personality": _str,
    "default_provider": _str,
}


def _defaults(settings: Settings) -> dict[str, Any]:
    return {
        "llm_model": settings.llm_model,
        "temperature": settings.default_temperature,
        "memory_require_approval": settings.memory_require_approval,
        "memory_auto_save": settings.memory_auto_save,
        "web_search_enabled": False,
        "web_search_model": settings.web_search_model,
        "canvas_enabled": True,
        "default_personality": "violet.default",
        "default_provider": settings.llm_provider,
    }


class PreferencesStore:
    """JSON-backed overrides merged over Settings defaults. Pure I/O, no network."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, OSError):
            return {}

    def overridden(self) -> list[str]:
        return [k for k in self._load() if k in EDITABLE_KEYS]

    def defaults(self, settings: Settings) -> dict[str, Any]:
        return _defaults(settings)

    def effective(self, settings: Settings) -> dict[str, Any]:
        values = _defaults(settings)
        for key, value in self._load().items():
            if key in EDITABLE_KEYS:
                values[key] = value
        return values

    def patch(self, changes: dict[str, Any]) -> dict[str, Any]:
        for key, value in changes.items():
            if key not in EDITABLE_KEYS:
                raise ValueError(f"unknown or non-editable key: {key}")
            if not EDITABLE_KEYS[key](value):
                raise ValueError(f"invalid value for {key}: {value!r}")
        current = self._load()
        current.update(changes)
        current = {k: v for k, v in current.items() if k in EDITABLE_KEYS}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        return current
```

- [ ] **Step 5: Run the store tests to verify they pass**

Run: `cd services/assistant-core && python -m pytest tests/test_preferences.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Write the settings router**

```python
# services/assistant-core/src/violet_assistant/routes/settings.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from violet_assistant.config import Settings
from violet_assistant.preferences.store import PreferencesStore


class SettingsPatch(BaseModel):
    model_config = {"extra": "allow"}


def create_settings_router(store: PreferencesStore, settings: Settings) -> APIRouter:
    router = APIRouter()

    def _payload() -> dict:
        return {
            "values": store.effective(settings),
            "defaults": store.defaults(settings),
            "overridden": store.overridden(),
        }

    @router.get("/api/settings")
    async def get_settings() -> dict:
        return _payload()

    @router.patch("/api/settings")
    async def patch_settings(patch: SettingsPatch) -> dict:
        try:
            store.patch(patch.model_dump(exclude_unset=True))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _payload()

    return router
```

- [ ] **Step 7: Wire the store + router in `main.py`**

After `store.initialize()` (and near other builders), add:

```python
    from violet_assistant.preferences.store import PreferencesStore
    from violet_assistant.routes.settings import create_settings_router

    preferences = PreferencesStore(active_settings.repo_root / "data" / "preferences.json")
```

Then with the other `app.include_router(...)` calls add:

```python
    app.include_router(create_settings_router(preferences, active_settings))
```

Pass `preferences` into the orchestrator constructor call (see Task 2 — add `preferences=preferences`).

- [ ] **Step 8: Add an endpoint test**

```python
# append to services/assistant-core/tests/test_preferences.py
from fastapi.testclient import TestClient

from violet_assistant.main import create_app


def test_settings_endpoints_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path/'v.db'}")
    app = create_app(load_settings(tmp_path))
    client = TestClient(app)
    body = client.get("/api/settings").json()
    assert "temperature" in body["values"]
    patched = client.patch("/api/settings", json={"temperature": 0.7}).json()
    assert patched["values"]["temperature"] == 0.7
    assert "temperature" in patched["overridden"]
    bad = client.patch("/api/settings", json={"temperature": 9})
    assert bad.status_code == 422
```

- [ ] **Step 9: Run the full preferences suite**

Run: `cd services/assistant-core && python -m pytest tests/test_preferences.py -v`
Expected: PASS (5 tests). If `create_app` signature differs, pass settings positionally as existing tests do (see `tests/test_providers_and_sessions.py`).

- [ ] **Step 10: Log + commit**

Write `logs/preferences-settings-api_2026-07-25_log.md` from the template, then:

```bash
git add services/assistant-core/src/violet_assistant/preferences services/assistant-core/src/violet_assistant/routes/settings.py services/assistant-core/src/violet_assistant/config.py services/assistant-core/src/violet_assistant/main.py services/assistant-core/tests/test_preferences.py logs/preferences-settings-api_2026-07-25_log.md
git commit -m "feat: runtime-editable preferences store + /api/settings"
```

---

### Task 2: Explicit-skill + web-search routing in chat

**Files:**
- Modify: `services/assistant-core/src/violet_assistant/schemas/chat.py` (add `skill_id`, `web_search` to `ChatRequest`; add `citations` to `ChatResponse`)
- Modify: `services/assistant-core/src/violet_assistant/skills/registry.py` (add `get`)
- Create: `services/assistant-core/src/violet_assistant/web/__init__.py`
- Create: `services/assistant-core/src/violet_assistant/web/search.py`
- Modify: `services/assistant-core/src/violet_assistant/orchestrator/chat_orchestrator.py` (accept `preferences`, `web_provider`; new precedence branches; use effective temperature/model)
- Modify: `services/assistant-core/src/violet_assistant/main.py` (build web provider, pass to orchestrator)
- Test: `services/assistant-core/tests/test_chat_orchestrator.py` (extend), `services/assistant-core/tests/test_web_search.py`

**Interfaces:**
- Consumes: `PreferencesStore` (Task 1), `LLMProvider`, `SkillEngine`, `SkillRegistry`.
- Produces: `SkillRegistry.get(skill_id) -> Skill | None`; `web_answer(provider, model, messages) -> WebAnswer(text, citations)`; `ChatRequest.skill_id: str | None`, `ChatRequest.web_search: bool`; `ChatResponse.citations: list[str]`.

- [ ] **Step 1: Write failing orchestrator + registry tests**

Read `tests/test_chat_orchestrator.py` first to reuse its fixtures/fakes. Add:

```python
# services/assistant-core/tests/test_web_search.py
from __future__ import annotations

from violet_assistant.web.search import WebAnswer, parse_web_response


def test_parse_web_response_extracts_text_and_citations():
    raw = {
        "choices": [
            {
                "message": {
                    "content": "Answer.",
                    "annotations": [
                        {"type": "url_citation", "url_citation": {"url": "https://a.example"}},
                        {"type": "url_citation", "url_citation": {"url": "https://b.example"}},
                    ],
                }
            }
        ]
    }
    result = parse_web_response(raw)
    assert isinstance(result, WebAnswer)
    assert result.text == "Answer."
    assert result.citations == ["https://a.example", "https://b.example"]


def test_parse_web_response_without_annotations():
    raw = {"choices": [{"message": {"content": "Hi"}}]}
    assert parse_web_response(raw) == WebAnswer(text="Hi", citations=[])
```

For the registry, add to `tests/test_skills.py`:

```python
def test_registry_get_returns_skill_by_id(tmp_path):
    from violet_assistant.skills.registry import SkillRegistry
    (tmp_path / "chart.json").write_text(
        '{"id":"chart","name":"Chart","kind":"chartjs","triggers":["chart"],"prompt":"p"}',
        encoding="utf-8",
    )
    reg = SkillRegistry(tmp_path)
    assert reg.get("chart").name == "Chart"
    assert reg.get("nope") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/assistant-core && python -m pytest tests/test_web_search.py tests/test_skills.py::test_registry_get_returns_skill_by_id -v`
Expected: FAIL (`violet_assistant.web` missing; `get` undefined).

- [ ] **Step 3: Add `SkillRegistry.get`**

In `skills/registry.py`, add a method:

```python
    def get(self, skill_id: str) -> Skill | None:
        for skill in self.list_skills():
            if skill.id == skill_id:
                return skill
        return None
```

- [ ] **Step 4: Add the web search module**

```python
# services/assistant-core/src/violet_assistant/web/__init__.py
```

```python
# services/assistant-core/src/violet_assistant/web/search.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from violet_assistant.llm.base import LLMOptions, LLMProvider, Message


@dataclass(frozen=True)
class WebAnswer:
    text: str
    citations: list[str] = field(default_factory=list)


def parse_web_response(raw: dict[str, Any]) -> WebAnswer:
    """Extract answer text + OpenRouter url_citation annotations from a raw response."""
    message = raw["choices"][0]["message"]
    text = (message.get("content") or "").strip()
    citations: list[str] = []
    for note in message.get("annotations") or []:
        if note.get("type") == "url_citation":
            url = (note.get("url_citation") or {}).get("url")
            if url and url not in citations:
                citations.append(url)
    return WebAnswer(text=text, citations=citations)


async def web_answer(
    provider: LLMProvider, model: str, messages: Sequence[Message]
) -> WebAnswer:
    """Ask an OpenRouter-backed provider with web search on (model + ':online').

    The provider must expose `_request_json` (OpenAICompatibleProvider does); we call
    the raw endpoint so we can read citation annotations the LLMResponse drops.
    """
    import asyncio

    online_model = model if model.endswith(":online") else f"{model}:online"
    payload = {
        "model": online_model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "temperature": LLMOptions(model=online_model).temperature,
        "stream": False,
    }
    raw = await asyncio.to_thread(
        provider._request_json, "POST", "/chat/completions", payload  # noqa: SLF001
    )
    return parse_web_response(raw)
```

- [ ] **Step 5: Extend the chat schemas**

In `schemas/chat.py`, add to `ChatRequest`:

```python
    skill_id: str | None = None
    web_search: bool = False
```

Add to `ChatResponse`:

```python
    citations: list[str] = Field(default_factory=list)
```

- [ ] **Step 6: Update the orchestrator**

In `chat_orchestrator.py`:
- Add constructor params `preferences: "PreferencesStore | None" = None` and `web_provider: LLMProvider | None = None`; store on `self`.
- After computing `history`/`messages`, read effective prefs (guarding for None), then replace the existing `base_options = LLMOptions(...)` block with the prefs-aware version:

```python
        prefs = (
            self.preferences.effective(self.settings) if self.preferences else {}
        )
        base_options = LLMOptions(
            model=prefs.get("llm_model", self.settings.llm_model),
            temperature=prefs.get("temperature", self.settings.default_temperature),
            metadata={
                "personality_id": profile.id,
                "personality_name": profile.name,
            },
        )
```

- Add `citations: list[str] = []` near `artifacts`.
- Insert new precedence branches. The chain becomes: mock → explicit agent → **web-search** → **explicit skill** → auto skill → auto agent → cascade → provider. Concretely, after the `explicit_agent` branch and before the auto `skill` branch, insert:

```python
        explicit_skill = (
            self.skill_registry.get(request.skill_id)
            if (self.skill_registry is not None and request.skill_id)
            else None
        )
```

and change the branch ladder so it reads:

```python
        if is_mock:
            llm_response = await self._select_provider(request.provider).chat(
                messages, base_options
            )
        elif explicit_agent is not None and self.agent_runner is not None:
            llm_response = await self.agent_runner.run(explicit_agent, messages)
            agent_used = explicit_agent.id
        elif request.web_search and self.web_provider is not None:
            from violet_assistant.web.search import web_answer

            answer = await web_answer(
                self.web_provider,
                prefs.get("web_search_model", self.settings.web_search_model),
                messages,
            )
            llm_response = LLMResponse(text=answer.text, emotion="focused")
            citations = answer.citations
        elif explicit_skill is not None and self.skill_engine is not None:
            intro, artifact_dicts = await self.skill_engine.generate(
                explicit_skill, request.content
            )
            llm_response = LLMResponse(text=intro, emotion="focused")
            artifacts = [Artifact.model_validate(item) for item in artifact_dicts]
        elif skill is not None and self.skill_engine is not None:
            intro, artifact_dicts = await self.skill_engine.generate(skill, request.content)
            llm_response = LLMResponse(text=intro, emotion="focused")
            artifacts = [Artifact.model_validate(item) for item in artifact_dicts]
        elif (
            self.agent_registry is not None
            and self.agent_runner is not None
            and (detected_agent := self.agent_registry.detect(request.content)) is not None
        ):
            llm_response = await self.agent_runner.run(detected_agent, messages)
            agent_used = detected_agent.id
        elif self.cascade is not None:
            result = await self.cascade.respond(messages, base_options)
            llm_response = LLMResponse(text=result.text, emotion=result.emotion)
        else:
            llm_response = await self._select_provider(request.provider).chat(
                messages, base_options
            )
```

- Add `citations=citations` to the returned `ChatResponse(...)`.

- [ ] **Step 7: Build the web provider in `main.py`**

After the skill_engine block, add:

```python
    web_provider = None
    if active_settings.web_search_api_key:
        web_provider = OpenAICompatibleProvider(
            base_url=active_settings.web_search_base_url,
            api_key=active_settings.web_search_api_key,
            timeout_seconds=active_settings.llm_timeout_seconds,
            default_headers={"HTTP-Referer": "https://localhost/violet", "X-Title": "Violet"},
        )
```

Add `preferences=preferences` and `web_provider=web_provider` to the `ChatOrchestrator(...)` call.

- [ ] **Step 8: Add orchestrator routing tests**

In `tests/test_chat_orchestrator.py`, following its existing fake-provider pattern, add a test that a `ChatRequest(skill_id="chart", ...)` invokes `skill_engine.generate` with the chart skill, and a test that `web_search=True` with a fake web provider returns the web text + citations. (Use the module's existing fakes; assert on `response.text`/`response.citations`/`response.artifacts`.)

- [ ] **Step 9: Run backend suite**

Run: `cd services/assistant-core && python -m pytest -q`
Expected: PASS (existing + new). Fix any fixture wiring (orchestrator now takes `preferences`/`web_provider` kwargs — both optional, so existing tests keep working).

- [ ] **Step 10: Log + commit**

Write `logs/chat-explicit-skill-websearch_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/web services/assistant-core/src/violet_assistant/schemas/chat.py services/assistant-core/src/violet_assistant/skills/registry.py services/assistant-core/src/violet_assistant/orchestrator/chat_orchestrator.py services/assistant-core/src/violet_assistant/main.py services/assistant-core/tests/test_web_search.py services/assistant-core/tests/test_chat_orchestrator.py services/assistant-core/tests/test_skills.py logs/chat-explicit-skill-websearch_2026-07-25_log.md
git commit -m "feat: explicit-skill invocation + web-search routing in chat"
```

---

### Task 3: URL fetch/crawl tool with SSRF guard

**Files:**
- Create: `services/assistant-core/src/violet_assistant/web/fetch.py`
- Create: `services/assistant-core/src/violet_assistant/routes/fetch.py`
- Modify: `services/assistant-core/src/violet_assistant/main.py` (include router)
- Test: `services/assistant-core/tests/test_web_fetch.py`

**Interfaces:**
- Produces: `extract_text(html: str) -> tuple[str, str]` (returns `(title, text)`); `is_blocked_host(host: str) -> bool`; `fetch_url(url: str, max_bytes: int = 2_000_000) -> FetchResult`; `POST /api/fetch {url} -> {url,title,text,chars,truncated}`.

- [ ] **Step 1: Write failing tests**

```python
# services/assistant-core/tests/test_web_fetch.py
from __future__ import annotations

import pytest

from violet_assistant.web.fetch import extract_text, is_blocked_host


def test_extract_text_strips_scripts_and_reads_title():
    html = "<html><head><title>Hi</title></head><body><p>Hello</p><script>bad()</script></body></html>"
    title, text = extract_text(html)
    assert title == "Hi"
    assert "Hello" in text
    assert "bad()" not in text


@pytest.mark.parametrize(
    "host",
    ["localhost", "127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.1.1", "::1"],
)
def test_blocks_internal_hosts(host):
    assert is_blocked_host(host) is True


def test_allows_public_host():
    assert is_blocked_host("example.com") is False
```

- [ ] **Step 2: Run to verify failure**

Run: `cd services/assistant-core && python -m pytest tests/test_web_fetch.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement the fetch module (stdlib only)**

```python
# services/assistant-core/src/violet_assistant/web/fetch.py
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib import error, request
from urllib.parse import urlparse

_SKIP_TAGS = {"script", "style", "noscript", "head"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def text(self) -> str:
        return "\n".join(self._parts)


def extract_text(html: str) -> tuple[str, str]:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.title.strip(), parser.text()


def is_blocked_host(host: str) -> bool:
    host = host.strip("[]").lower()
    if host in {"localhost", ""}:
        return True
    candidates: list[str] = [host]
    try:
        candidates = [info[4][0] for info in socket.getaddrinfo(host, None)]
    except socket.gaierror:
        pass
    for addr in candidates:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


@dataclass(frozen=True)
class FetchResult:
    url: str
    title: str
    text: str
    chars: int
    truncated: bool


def fetch_url(url: str, max_bytes: int = 2_000_000) -> FetchResult:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("only http(s) URLs are allowed")
    if not parsed.hostname or is_blocked_host(parsed.hostname):
        raise ValueError("host is not allowed")
    req = request.Request(url, headers={"User-Agent": "VioletAssistant/0.1"})
    try:
        with request.urlopen(req, timeout=15) as resp:
            raw = resp.read(max_bytes + 1)
    except error.URLError as exc:
        raise ValueError(f"could not fetch: {exc.reason}") from exc
    truncated = len(raw) > max_bytes
    html = raw[:max_bytes].decode("utf-8", errors="replace")
    title, text = extract_text(html)
    return FetchResult(url=url, title=title, text=text, chars=len(text), truncated=truncated)
```

- [ ] **Step 4: Run module tests**

Run: `cd services/assistant-core && python -m pytest tests/test_web_fetch.py -v`
Expected: PASS.

- [ ] **Step 5: Add the router**

```python
# services/assistant-core/src/violet_assistant/routes/fetch.py
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from violet_assistant.web.fetch import fetch_url


class FetchRequest(BaseModel):
    url: str


def create_fetch_router() -> APIRouter:
    router = APIRouter()

    @router.post("/api/fetch")
    async def fetch(body: FetchRequest) -> dict:
        try:
            result = await asyncio.to_thread(fetch_url, body.url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "url": result.url,
            "title": result.title,
            "text": result.text,
            "chars": result.chars,
            "truncated": result.truncated,
        }

    return router
```

Include it in `main.py` with the other routers: `app.include_router(create_fetch_router())` (import at top).

- [ ] **Step 6: Add an endpoint block test**

```python
# append to tests/test_web_fetch.py
from fastapi.testclient import TestClient

from violet_assistant.config import load_settings
from violet_assistant.main import create_app


def test_fetch_endpoint_blocks_localhost(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path/'v.db'}")
    client = TestClient(create_app(load_settings(tmp_path)))
    resp = client.post("/api/fetch", json={"url": "http://127.0.0.1:8000/secret"})
    assert resp.status_code == 400
```

- [ ] **Step 7: Run + log + commit**

Run: `cd services/assistant-core && python -m pytest tests/test_web_fetch.py -q` → PASS.
Write `logs/url-fetch-tool_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/web/fetch.py services/assistant-core/src/violet_assistant/routes/fetch.py services/assistant-core/src/violet_assistant/main.py services/assistant-core/tests/test_web_fetch.py logs/url-fetch-tool_2026-07-25_log.md
git commit -m "feat: /api/fetch URL crawl tool with SSRF guard"
```

---

### Task 4: Frontend API additions + slash skill palette

**Files:**
- Modify: `apps/web-client/src/lib/api.ts` (skill/web params on `sendChat`; `fetchSettings`, `patchSettings`, `fetchUrl`; `AppSettings` type; `citations` on `ChatResponse`)
- Create: `apps/web-client/src/components/SkillPalette.tsx`
- Modify: `apps/web-client/src/components/Composer.tsx` (slash detection, palette, skill chip, web globe toggle)
- Modify: `apps/web-client/src/App.tsx` (skill state, web state, thread through)
- Verify: `cd apps/web-client && npm run build`

**Interfaces:**
- Consumes: `GET /api/skills`, `POST /api/chat` (`skill_id`, `web_search`), `GET/PATCH /api/settings`, `POST /api/fetch`.
- Produces: `sendChat(content, sessionId, personalityId, provider?, agent?, opts?: {skillId?: string; webSearch?: boolean})`; `AppSettings` type; `fetchSettings()`, `patchSettings(changes)`, `fetchUrl(url)`.

- [ ] **Step 1: Extend `lib/api.ts`**

Add `citations` to `ChatResponse`:

```typescript
export type ChatResponse = {
  // ...existing fields...
  citations: string[];
};
```

Change `sendChat` to accept an options object (keep positional args for back-compat):

```typescript
export async function sendChat(
  content: string,
  sessionId: string | null,
  personalityId: string,
  provider?: string | null,
  agent?: string | null,
  opts?: { skillId?: string | null; webSearch?: boolean },
): Promise<ChatResponse> {
  return requestJson<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({
      content,
      session_id: sessionId,
      personality_id: personalityId,
      provider: provider ?? null,
      agent: agent ?? null,
      skill_id: opts?.skillId ?? null,
      web_search: opts?.webSearch ?? false,
    }),
  });
}
```

Add settings + fetch helpers:

```typescript
export type AppSettings = {
  values: Record<string, string | number | boolean>;
  defaults: Record<string, string | number | boolean>;
  overridden: string[];
};

export async function fetchSettings(): Promise<AppSettings> {
  return requestJson<AppSettings>("/api/settings");
}

export async function patchSettings(
  changes: Record<string, string | number | boolean>,
): Promise<AppSettings> {
  return requestJson<AppSettings>("/api/settings", {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}

export type FetchResult = {
  url: string;
  title: string;
  text: string;
  chars: number;
  truncated: boolean;
};

export async function fetchUrl(url: string): Promise<FetchResult> {
  return requestJson<FetchResult>("/api/fetch", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}
```

- [ ] **Step 2: Create the skill palette component**

```tsx
// apps/web-client/src/components/SkillPalette.tsx
import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { SkillInfo, fetchSkills } from "../lib/api";

type Props = {
  query: string; // text after the leading "/"
  onPick: (skill: SkillInfo) => void;
  onClose: () => void;
};

export function SkillPalette({ query, onPick, onClose }: Props) {
  const [skills, setSkills] = useState<SkillInfo[]>([]);

  useEffect(() => {
    fetchSkills()
      .then((r) => setSkills(r.enabled ? r.items : []))
      .catch(() => setSkills([]));
  }, []);

  const q = query.toLowerCase();
  const filtered = skills.filter(
    (s) =>
      s.id.toLowerCase().includes(q) ||
      s.name.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q),
  );
  if (filtered.length === 0) return null;

  return (
    <div className="absolute bottom-full mb-2 left-0 w-full max-w-md bg-white border border-navy-700/20 rounded-2xl shadow-xl overflow-hidden z-30">
      <div className="px-3 py-2 text-[10px] uppercase tracking-wider text-steel/60 border-b border-navy-700/10 flex items-center gap-1.5">
        <Sparkles size={11} className="text-steel-highlight" /> Skills
      </div>
      <ul className="max-h-64 overflow-y-auto custom-scrollbar">
        {filtered.map((s) => (
          <li key={s.id}>
            <button
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                onPick(s);
              }}
              className="w-full text-left px-3 py-2 hover:bg-steel-ice transition flex flex-col"
            >
              <span className="text-sm font-medium text-steel-dark">
                /{s.id} · {s.name}
              </span>
              <span className="text-[11px] text-steel/60 truncate">{s.description}</span>
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onMouseDown={(e) => {
          e.preventDefault();
          onClose();
        }}
        className="w-full text-[10px] text-steel/50 py-1.5 hover:bg-steel-ice"
      >
        Esc to dismiss
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Wire palette + chip + globe into `Composer.tsx`**

Add props to `ComposerProps`:

```typescript
  activeSkill: { id: string; name: string } | null;
  onPickSkill: (skill: { id: string; name: string } | null) => void;
  webSearchAvailable: boolean;
  webSearchOn: boolean;
  onToggleWebSearch: () => void;
```

Inside the component:
- Import `SkillPalette` and `Globe`/`Sparkles`/`X` from lucide-react.
- Derive `const slashQuery = value.startsWith("/") ? value.slice(1) : null;` and show `<SkillPalette>` when `slashQuery !== null && !activeSkill`.
- On pick: `onPickSkill({ id: skill.id, name: skill.name }); onChange("");`.
- Render an active-skill chip (like the attachment chip) with an `X` that calls `onPickSkill(null)`.
- Add a globe toggle button next to the mic (only when `webSearchAvailable`), highlighted when `webSearchOn`, calling `onToggleWebSearch`.
- On `Esc` keydown in the input, if `slashQuery !== null` clear the slash text.

- [ ] **Step 4: Thread state through `App.tsx`**

- Add state: `const [activeSkill, setActiveSkill] = useState<{id:string;name:string}|null>(null);` and `const [webSearchOn, setWebSearchOn] = useState(false);` and `const [appSettings, setAppSettings] = useState<AppSettings|null>(null);`.
- On mount, `fetchSettings().then(setAppSettings).catch(()=>{})`.
- `webSearchAvailable = Boolean(appSettings?.values.web_search_enabled)`.
- In `send`, pass options: `await sendChat(sentContent, sessionId, personalityId, selectedProvider, selectedAgent || null, { skillId: activeSkill?.id ?? null, webSearch: webSearchOn })`.
- After a successful send, `setActiveSkill(null)` (one-shot). Keep `webSearchOn` sticky.
- Store `response.citations` on the assistant message (extend `ChatMessage` type in `api.ts` with `citations?: string[]`) and render them (Task 7).
- Extend `composerProps` with `activeSkill`, `onPickSkill: setActiveSkill`, `webSearchAvailable`, `webSearchOn`, `onToggleWebSearch: () => setWebSearchOn(v=>!v)`.

- [ ] **Step 5: Build**

Run: `cd apps/web-client && npm run build`
Expected: type-checks and builds with no errors.

- [ ] **Step 6: Log + commit**

Write `logs/slash-palette-web-toggle_2026-07-25_log.md`, then:

```bash
git add apps/web-client/src/lib/api.ts apps/web-client/src/components/SkillPalette.tsx apps/web-client/src/components/Composer.tsx apps/web-client/src/App.tsx logs/slash-palette-web-toggle_2026-07-25_log.md
git commit -m "feat: slash skill palette + web-search toggle in composer"
```

---

### Task 5: Canvas side panel

**Files:**
- Modify: `apps/web-client/src/components/ArtifactView.tsx` (export `ChartArtifact`, `HtmlArtifact`, `FileArtifact`; add compact card mode)
- Create: `apps/web-client/src/components/CanvasPanel.tsx`
- Modify: `apps/web-client/src/App.tsx` (canvas state, session artifacts, layout split)
- Modify: `apps/web-client/src/components/ChatTimeline.tsx` (pass an `onOpenArtifact` handler down to message artifacts) — inspect first to match its props
- Verify: `cd apps/web-client && npm run build`

**Interfaces:**
- Consumes: `Artifact` type; `canvas_enabled` from `AppSettings`.
- Produces: `CanvasPanel({ artifacts, activeId, onSelect, onClose })`; `ArtifactView` gains `compact?: boolean` and `onOpen?: () => void`.

- [ ] **Step 1: Refactor `ArtifactView.tsx` to export sub-renderers**

Change `function ChartArtifact`/`HtmlArtifact`/`FileArtifact` to `export function ...` (no behavior change). Add to `ArtifactView` a `compact` prop: when `compact` is true, render just the header row (icon + title + kind badge) as a button that calls `onOpen`, instead of the full renderer. Signature:

```tsx
export function ArtifactView({
  artifact,
  compact = false,
  onOpen,
}: {
  artifact: Artifact;
  compact?: boolean;
  onOpen?: () => void;
}) { /* ... */ }
```

- [ ] **Step 2: Create `CanvasPanel.tsx`**

```tsx
// apps/web-client/src/components/CanvasPanel.tsx
import { X } from "lucide-react";
import { Artifact } from "../lib/api";
import { ChartArtifact, HtmlArtifact, FileArtifact } from "./ArtifactView";

type Props = {
  artifacts: Artifact[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onClose: () => void;
};

export function CanvasPanel({ artifacts, activeId, onSelect, onClose }: Props) {
  const active = artifacts.find((a) => a.id === activeId) ?? artifacts[0];
  if (!active) return null;
  const body =
    active.kind === "chartjs" ? (
      <ChartArtifact artifact={active} />
    ) : active.kind === "docx" || active.kind === "pptx" ? (
      <FileArtifact artifact={active} />
    ) : (
      <HtmlArtifact artifact={active} />
    );
  return (
    <aside className="h-full w-full lg:w-[46%] shrink-0 border-l border-navy-700/20 bg-white flex flex-col">
      <header className="flex items-center gap-2 px-4 py-3 border-b border-navy-700/15">
        <span className="text-sm font-semibold text-steel-dark truncate">
          {active.title || "Canvas"}
        </span>
        <span className="text-[10px] uppercase tracking-wider text-steel/50">{active.kind}</span>
        <button
          onClick={onClose}
          className="ml-auto w-7 h-7 rounded-lg flex items-center justify-center text-steel hover:bg-steel-ice"
          title="Close canvas"
        >
          <X size={15} />
        </button>
      </header>
      {artifacts.length > 1 && (
        <div className="flex gap-1.5 px-3 py-2 overflow-x-auto border-b border-navy-700/10">
          {artifacts.map((a) => (
            <button
              key={a.id}
              onClick={() => onSelect(a.id)}
              className={`px-2.5 py-1 rounded-lg text-[11px] whitespace-nowrap border transition ${
                a.id === active.id
                  ? "bg-steel-highlight/10 text-steel-highlight border-steel-highlight/30"
                  : "bg-steel-ice text-steel border-navy-700/15"
              }`}
            >
              {a.title || a.kind}
            </button>
          ))}
        </div>
      )}
      <div className="flex-1 overflow-y-auto custom-scrollbar">{body}</div>
    </aside>
  );
}
```

- [ ] **Step 3: Wire canvas into `App.tsx`**

- State: `const [canvasOpen, setCanvasOpen] = useState(false);` `const [canvasArtifactId, setCanvasArtifactId] = useState<string|null>(null);`
- Derive session artifacts: `const sessionArtifacts = useMemo(() => messages.flatMap(m => m.artifacts ?? []), [messages]);`
- `canvasEnabled = appSettings?.values.canvas_enabled !== false;`
- Add an `openArtifact(id)` handler: `setCanvasArtifactId(id); setCanvasOpen(true);`
- Pass `onOpenArtifact={canvasEnabled ? openArtifact : undefined}` down through `ChatTimeline` to each `ArtifactView` (render `compact` when `canvasEnabled && onOpenArtifact` is set; otherwise render full inline as today).
- Layout: wrap `<main>` and the canvas in a flex row. When `canvasOpen && canvasEnabled`, render `<CanvasPanel artifacts={sessionArtifacts} activeId={canvasArtifactId} onSelect={setCanvasArtifactId} onClose={() => setCanvasOpen(false)} />` beside `<main>`. On screens below `lg`, give the panel `fixed inset-0 z-40` (full-screen overlay) via responsive classes already in `CanvasPanel`'s wrapper — adjust wrapper to `fixed inset-0 z-40 lg:static lg:inset-auto`.

- [ ] **Step 4: Update `ChatTimeline.tsx`**

Read the file, add an optional `onOpenArtifact?: (id: string) => void` prop, and where it renders `<ArtifactView artifact={...} />` pass `compact={Boolean(onOpenArtifact)}` and `onOpen={() => onOpenArtifact?.(artifact.id)}`.

- [ ] **Step 5: Build + manual smoke**

Run: `cd apps/web-client && npm run build` → clean.
Manual: with an artifact-producing skill, confirm the inline card opens the canvas, the gallery switches artifacts, and close returns to full-width chat.

- [ ] **Step 6: Log + commit**

Write `logs/canvas-panel_2026-07-25_log.md`, then:

```bash
git add apps/web-client/src/components/ArtifactView.tsx apps/web-client/src/components/CanvasPanel.tsx apps/web-client/src/components/ChatTimeline.tsx apps/web-client/src/App.tsx logs/canvas-panel_2026-07-25_log.md
git commit -m "feat: canvas side panel for artifacts"
```

---

### Task 6: Expanded Settings modal (skills list + preference controls)

**Files:**
- Modify: `apps/web-client/src/components/SettingsModal.tsx` (skills list section + preference controls)
- Modify: `apps/web-client/src/App.tsx` (pass skills, settings, and a `patchSettings` handler; open Skill Lab from settings)
- Verify: `cd apps/web-client && npm run build`

**Interfaces:**
- Consumes: `fetchSkills`, `AppSettings`, `patchSettings`.
- Produces: settings modal that reads/writes preferences and lists skills.

- [ ] **Step 1: Load skills + settings in `App.tsx`**

- Add `const [skills, setSkills] = useState<SkillInfo[]>([]);` and load via `fetchSkills().then(r => setSkills(r.enabled ? r.items : [])).catch(()=>{})` on mount.
- Add a handler:

```tsx
async function handlePatchSettings(changes: Record<string, string | number | boolean>) {
  try {
    const next = await patchSettings(changes);
    setAppSettings(next);
  } catch (e) {
    setStatus({ tone: "error", text: e instanceof Error ? e.message : "Settings failed" });
  }
}
```

- Pass to `SettingsModal`: `skills`, `settings={appSettings}`, `onPatchSettings={handlePatchSettings}`, `onOpenSkillLab={() => { setSettingsOpen(false); setSkillLabOpen(true); }}`.

- [ ] **Step 2: Add sections to `SettingsModal.tsx`**

Extend `SettingsModalProps` with:

```typescript
  skills: SkillInfo[];
  settings: AppSettings | null;
  onPatchSettings: (changes: Record<string, string | number | boolean>) => void;
  onOpenSkillLab: () => void;
```

Add a **Behavior** section (below Persona) with:
- Temperature range input (0–2, step 0.1) bound to `settings?.values.temperature`, `onChange` → `onPatchSettings({ temperature: Number(e.target.value) })`.
- Toggle buttons for `web_search_enabled`, `canvas_enabled`, `memory_require_approval` that call `onPatchSettings({ [key]: !current })`.
- A small text input for `web_search_model` (only when `web_search_enabled`).

Add a **Skills** section listing `skills` (name · description · kind badge) with a button "Open Skill Lab" → `onOpenSkillLab`. Use the same card styling as the agents list.

Guard all reads with `settings?.values?.[key]` and render the section only when `settings` is loaded.

- [ ] **Step 3: Build**

Run: `cd apps/web-client && npm run build` → clean.

- [ ] **Step 4: Log + commit**

Write `logs/settings-modal-skills-prefs_2026-07-25_log.md`, then:

```bash
git add apps/web-client/src/components/SettingsModal.tsx apps/web-client/src/App.tsx logs/settings-modal-skills-prefs_2026-07-25_log.md
git commit -m "feat: settings modal skills list + editable preferences"
```

---

### Task 7: Citations rendering + final verification

**Files:**
- Modify: `apps/web-client/src/lib/api.ts` (add `citations?: string[]` to `ChatMessage`)
- Modify: `apps/web-client/src/App.tsx` (store `response.citations` on the assistant message)
- Modify: `apps/web-client/src/components/ChatTimeline.tsx` (render a compact citation list under an assistant message that has citations)
- Verify: full backend suite + frontend build

**Interfaces:**
- Consumes: `ChatResponse.citations`.

- [ ] **Step 1: Add `citations` to `ChatMessage`**

In `api.ts`:

```typescript
export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  artifacts?: Artifact[];
  citations?: string[];
};
```

- [ ] **Step 2: Persist citations in `App.tsx`**

In `send`, where the assistant message is appended, add `citations: response.citations`.

- [ ] **Step 3: Render citations in `ChatTimeline.tsx`**

For an assistant message with `citations?.length`, render below the text:

```tsx
{message.citations && message.citations.length > 0 && (
  <ul className="mt-2 space-y-1">
    {message.citations.map((url) => (
      <li key={url} className="text-[11px] truncate">
        <a href={url} target="_blank" rel="noopener noreferrer" className="text-steel-highlight hover:underline">
          {url}
        </a>
      </li>
    ))}
  </ul>
)}
```

- [ ] **Step 4: Full verification**

Run backend: `cd services/assistant-core && python -m pytest -q` → all PASS.
Run frontend: `cd apps/web-client && npm run build` → clean.
Manual smoke (backend running with an OpenRouter key + `web_search_enabled` on): `/chart` skill produces an artifact that opens in canvas; globe toggle returns a cited web answer; settings changes persist across reload (`data/preferences.json` written).

- [ ] **Step 5: Log + commit**

Write `logs/citations-final-verify_2026-07-25_log.md`, then:

```bash
git add apps/web-client/src/lib/api.ts apps/web-client/src/App.tsx apps/web-client/src/components/ChatTimeline.tsx logs/citations-final-verify_2026-07-25_log.md
git commit -m "feat: render web-search citations under answers"
```

---

## Notes for the implementer
- Read a file before modifying it; match existing Tailwind class conventions (`steel-*`, `navy-*`) and the frozen-dataclass / factory patterns already in the repo.
- The orchestrator's new constructor params are optional — existing tests and call sites keep working without them.
- `web_answer` calls the provider's `_request_json` to read citation annotations that `LLMResponse` drops; this is deliberate coupling to `OpenAICompatibleProvider` and is the only place that reaches into it.
- If `create_app` in tests needs settings, follow the existing pattern in `tests/test_providers_and_sessions.py`.
