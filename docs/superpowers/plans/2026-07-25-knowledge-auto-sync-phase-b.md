# Knowledge Auto-Sync (Phase B) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically keep the knowledge base in sync — no manual Reindex/Sync — via a background polling loop, controlled by a runtime toggle.

**Architecture:** An `AutoSyncScheduler` runs an async loop that re-runs the existing incremental `reindex(only=...)` — local on a fast interval, Google Drive on a slower one. Enabled/disabled live via a `knowledge_auto_sync` preference. Wired into FastAPI startup/shutdown; last-sync status surfaced through `GET /api/knowledge`. No new dependencies.

**Tech Stack:** Python 3.11, FastAPI, stdlib `asyncio`/`time`/`datetime`, pytest; React 18 + TS + Vite.

## Global Constraints

- Python `>=3.11`; backend root `services/assistant-core/src/violet_assistant`.
- Run tests from repo root: `python -m pytest -q`. Async tests: `@pytest.mark.asyncio`.
- No new runtime dependencies.
- The scheduler's cadence logic lives in `run_due(now)` with `now` injected, so it is unit-testable without real sleeping. The loop/`start`/`stop` is thin and not unit-tested.
- Auto-sync is **opt-in** (`knowledge_auto_sync` preference default false, seeded from `KNOWLEDGE_AUTO_SYNC`); the loop reads the preference **live** each tick.
- Test routers by awaiting endpoint callables directly (no `TestClient`/httpx).
- Every unit: tests + a `logs/{update}_{YYYY-MM-DD}_log.md` entry (template `logs/_TEMPLATE.md`) before committing. Date 2026-07-25.
- Frontend verified with `cd apps/web-client && npm run build`.

---

### Task 1: `knowledge_auto_sync` preference + settings fields

**Files:**
- Modify: `services/assistant-core/src/violet_assistant/preferences/store.py`
- Modify: `services/assistant-core/src/violet_assistant/config.py`
- Test: `services/assistant-core/tests/test_preferences.py` (extend)

**Interfaces:**
- Produces: editable preference `knowledge_auto_sync` (bool), default = `settings.knowledge_auto_sync`; `Settings.knowledge_auto_sync`, `knowledge_sync_interval_seconds`, `gdrive_sync_interval_seconds`.

- [ ] **Step 1: Write failing test**

```python
# append to services/assistant-core/tests/test_preferences.py
def test_knowledge_auto_sync_pref(tmp_path, settings):
    store = PreferencesStore(tmp_path / "preferences.json")
    assert store.effective(settings)["knowledge_auto_sync"] is False
    store.patch({"knowledge_auto_sync": True})
    assert store.effective(settings)["knowledge_auto_sync"] is True
    with pytest.raises(ValueError):
        store.patch({"knowledge_auto_sync": "yes"})
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_preferences.py::test_knowledge_auto_sync_pref -q`
Expected: FAIL (unknown key).

- [ ] **Step 3: Add settings fields (config.py)**

In the `Settings` dataclass, after the knowledge fields:

```python
    knowledge_auto_sync: bool = False
    knowledge_sync_interval_seconds: int = 30
    gdrive_sync_interval_seconds: int = 300
```

In `load_settings`:

```python
        knowledge_auto_sync=_env_bool("KNOWLEDGE_AUTO_SYNC", False),
        knowledge_sync_interval_seconds=int(os.getenv("KNOWLEDGE_SYNC_INTERVAL_SECONDS", "30")),
        gdrive_sync_interval_seconds=int(os.getenv("GDRIVE_SYNC_INTERVAL_SECONDS", "300")),
```

- [ ] **Step 4: Add the preference**

In `preferences/store.py`, add to `EDITABLE_KEYS`:

```python
    "knowledge_auto_sync": _is_bool,
```

And to `_defaults(settings)`:

```python
        "knowledge_auto_sync": settings.knowledge_auto_sync,
```

- [ ] **Step 5: Run + verify pass**

Run: `python -m pytest services/assistant-core/tests/test_preferences.py -q`
Expected: PASS.

- [ ] **Step 6: Log + commit**

Write `logs/auto-sync-preference_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/preferences/store.py services/assistant-core/src/violet_assistant/config.py services/assistant-core/tests/test_preferences.py logs/auto-sync-preference_2026-07-25_log.md
git commit -m "feat: knowledge_auto_sync preference + interval settings"
```

---

### Task 2: `AutoSyncScheduler`

**Files:**
- Create: `services/assistant-core/src/violet_assistant/knowledge/auto_sync.py`
- Test: `services/assistant-core/tests/test_auto_sync.py`

**Interfaces:**
- Produces: `AutoSyncScheduler(indexer, preferences, settings)` with `enabled()`, `async run_due(now: float) -> dict`, `status() -> dict`, `async start()`, `async stop()`.

- [ ] **Step 1: Write failing tests**

```python
# services/assistant-core/tests/test_auto_sync.py
from __future__ import annotations

import pytest

from violet_assistant.config import load_settings
from violet_assistant.knowledge.auto_sync import AutoSyncScheduler
from violet_assistant.preferences.store import PreferencesStore


class _FakeSource:
    def __init__(self, name):
        self.name = name


class _FakeIndexer:
    def __init__(self, sources, fail=False):
        self.sources = sources
        self.calls = []
        self.fail = fail

    async def reindex(self, full=False, only=None):
        if self.fail:
            raise RuntimeError("boom")
        self.calls.append(only)
        return {"indexed": 1, "skipped": 0, "removed": 0, "chunks": 2, "errors": [],
                "sources": {only: {"indexed": 1, "skipped": 0, "removed": 0, "chunks": 2, "errors": []}}}


def _sched(tmp_path, sources, enabled=True, fail=False):
    settings = load_settings(tmp_path)
    prefs = PreferencesStore(tmp_path / "preferences.json")
    if enabled:
        prefs.patch({"knowledge_auto_sync": True})
    return AutoSyncScheduler(_FakeIndexer(sources, fail=fail), prefs, settings), prefs


@pytest.mark.asyncio
async def test_disabled_does_nothing(tmp_path):
    sched, _ = _sched(tmp_path, [_FakeSource("local")], enabled=False)
    result = await sched.run_due(now=0.0)
    assert result["ran"] == []
    assert sched.indexer.calls == []


@pytest.mark.asyncio
async def test_local_runs_every_tick_gdrive_gated(tmp_path):
    sched, _ = _sched(tmp_path, [_FakeSource("local"), _FakeSource("gdrive")])
    r1 = await sched.run_due(now=0.0)      # local + gdrive (first time)
    assert set(r1["ran"]) == {"local", "gdrive"}
    r2 = await sched.run_due(now=10.0)     # only local (gdrive interval 300 not elapsed)
    assert r2["ran"] == ["local"]
    r3 = await sched.run_due(now=400.0)    # gdrive due again
    assert set(r3["ran"]) == {"local", "gdrive"}


@pytest.mark.asyncio
async def test_no_gdrive_source_skips_gdrive(tmp_path):
    sched, _ = _sched(tmp_path, [_FakeSource("local")])
    r = await sched.run_due(now=0.0)
    assert r["ran"] == ["local"]


@pytest.mark.asyncio
async def test_overlap_returns_in_progress(tmp_path):
    sched, _ = _sched(tmp_path, [_FakeSource("local")])
    await sched._lock.acquire()
    try:
        r = await sched.run_due(now=0.0)
        assert r == {"skipped": "in_progress"}
    finally:
        sched._lock.release()


@pytest.mark.asyncio
async def test_error_recorded_not_raised(tmp_path):
    sched, _ = _sched(tmp_path, [_FakeSource("local")], fail=True)
    await sched.run_due(now=0.0)  # must not raise
    assert sched.status()["last_sync"]["local"]["error"] == "boom"


@pytest.mark.asyncio
async def test_status_shape(tmp_path):
    sched, _ = _sched(tmp_path, [_FakeSource("local")])
    await sched.run_due(now=0.0)
    st = sched.status()
    assert st["enabled"] is True
    assert st["interval"] == 30
    assert st["gdrive_interval"] == 300
    assert st["last_sync"]["local"]["indexed"] == 1
    assert isinstance(st["last_sync"]["local"]["at"], str)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_auto_sync.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# knowledge/auto_sync.py
from __future__ import annotations

import asyncio
import datetime


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class AutoSyncScheduler:
    def __init__(self, indexer, preferences, settings) -> None:
        self.indexer = indexer
        self.preferences = preferences
        self.settings = settings
        self.interval = settings.knowledge_sync_interval_seconds
        self.gdrive_interval = settings.gdrive_sync_interval_seconds
        self._lock = asyncio.Lock()
        self._last_gdrive: float | None = None
        self._last_result: dict = {"local": None, "gdrive": None}
        self._task: asyncio.Task | None = None
        self._stopped = False

    def enabled(self) -> bool:
        if self.preferences is None:
            return bool(self.settings.knowledge_auto_sync)
        return bool(self.preferences.effective(self.settings).get("knowledge_auto_sync", False))

    def _has_gdrive(self) -> bool:
        return any(getattr(s, "name", "") == "gdrive" for s in self.indexer.sources)

    async def _sync(self, origin: str) -> None:
        try:
            report = await self.indexer.reindex(only=origin)
            per = report.get("sources", {}).get(origin, report)
            self._last_result[origin] = {
                "at": _now_iso(),
                "indexed": per.get("indexed", 0),
                "skipped": per.get("skipped", 0),
                "removed": per.get("removed", 0),
                "chunks": per.get("chunks", 0),
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 — one bad sync must not kill the loop
            self._last_result[origin] = {"at": _now_iso(), "error": str(exc)}

    async def run_due(self, now: float) -> dict:
        if not self.enabled():
            return {"ran": []}
        if self._lock.locked():
            return {"skipped": "in_progress"}
        ran: list[str] = []
        async with self._lock:
            await self._sync("local")
            ran.append("local")
            if self._has_gdrive() and (
                self._last_gdrive is None or now - self._last_gdrive >= self.gdrive_interval
            ):
                await self._sync("gdrive")
                self._last_gdrive = now
                ran.append("gdrive")
        return {"ran": ran}

    def status(self) -> dict:
        return {
            "enabled": self.enabled(),
            "interval": self.interval,
            "gdrive_interval": self.gdrive_interval,
            "last_sync": dict(self._last_result),
        }

    async def _loop(self) -> None:
        import time

        while not self._stopped:
            await asyncio.sleep(self.interval)
            try:
                await self.run_due(time.monotonic())
            except Exception:  # noqa: BLE001 — the loop must never die
                pass

    async def start(self) -> None:
        if self._task is None:
            self._stopped = False
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopped = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None
```

- [ ] **Step 4: Run + verify pass**

Run: `python -m pytest services/assistant-core/tests/test_auto_sync.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Log + commit**

Write `logs/auto-sync-scheduler_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/knowledge/auto_sync.py services/assistant-core/tests/test_auto_sync.py logs/auto-sync-scheduler_2026-07-25_log.md
git commit -m "feat: AutoSyncScheduler (interval polling, per-source cadence)"
```

---

### Task 3: App wiring + `auto_sync` in knowledge status

**Files:**
- Modify: `services/assistant-core/src/violet_assistant/main.py` (build scheduler, startup/shutdown, pass to router)
- Modify: `services/assistant-core/src/violet_assistant/routes/knowledge.py` (accept `scheduler`, add `auto_sync` to status)
- Test: `services/assistant-core/tests/test_knowledge_routes.py` (extend)

**Interfaces:**
- Produces: `create_knowledge_router(..., scheduler=None)`; `GET /api/knowledge` returns `auto_sync`.

- [ ] **Step 1: Write failing test**

```python
# append to services/assistant-core/tests/test_knowledge_routes.py
@pytest.mark.asyncio
async def test_status_includes_auto_sync(tmp_path):
    from violet_assistant.config import load_settings
    from violet_assistant.knowledge.auto_sync import AutoSyncScheduler
    from violet_assistant.preferences.store import PreferencesStore

    kdir = tmp_path / "knowledge"; kdir.mkdir()
    store = SqliteVectorStore(tmp_path / "k.db"); store.initialize()
    src = LocalFolderSource(kdir)
    indexer = KnowledgeIndexer(MockEmbedder(), store, [src])
    settings = load_settings(tmp_path)
    scheduler = AutoSyncScheduler(indexer, PreferencesStore(tmp_path / "p.json"), settings)
    router = create_knowledge_router(indexer, store, str(kdir), "mock", [src], None, settings, scheduler)
    body = await _endpoint(router, "GET")()
    assert body["auto_sync"]["enabled"] is False
    assert body["auto_sync"]["interval"] == 30
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest services/assistant-core/tests/test_knowledge_routes.py::test_status_includes_auto_sync -q`
Expected: FAIL (signature / key missing).

- [ ] **Step 3: Extend the router**

In `routes/knowledge.py`, add `scheduler=None` to the signature and the block to `status()`:

```python
def create_knowledge_router(
    indexer, store, knowledge_dir, model, sources=None, gdrive_source=None,
    settings=None, scheduler=None,
):
```

```python
        return {
            "dir": str(knowledge_dir),
            "provider": model,
            "enabled": indexer is not None,
            "doc_count": stats["doc_count"],
            "chunk_count": stats["chunk_count"],
            "docs": store.list_docs() if store else [],
            "sources": [s.status() for s in (sources or [])],
            "auto_sync": scheduler.status() if scheduler else {"enabled": False},
        }
```

- [ ] **Step 4: Wire `main.py`**

After the knowledge indexer is built (inside the `rag_provider == "vector"` block), build the scheduler:

```python
    knowledge_scheduler = None
    if knowledge_indexer is not None:
        from violet_assistant.knowledge.auto_sync import AutoSyncScheduler

        knowledge_scheduler = AutoSyncScheduler(
            knowledge_indexer, preferences, active_settings
        )
```

Pass it to the router:

```python
        create_knowledge_router(
            knowledge_indexer,
            knowledge_store,
            str(active_settings.knowledge_dir),
            knowledge_model,
            knowledge_sources,
            next((s for s in knowledge_sources if s.name == "gdrive"), None),
            active_settings,
            knowledge_scheduler,
        )
```

Register startup/shutdown after `app = FastAPI(...)` and after the scheduler exists (place the handlers near the end of `create_app`, before `return app`):

```python
    @app.on_event("startup")
    async def _start_autosync() -> None:  # pragma: no cover — lifecycle
        if knowledge_scheduler is not None:
            await knowledge_scheduler.start()

    @app.on_event("shutdown")
    async def _stop_autosync() -> None:  # pragma: no cover — lifecycle
        if knowledge_scheduler is not None:
            await knowledge_scheduler.stop()
```

- [ ] **Step 5: Run + verify pass**

Run: `python -m pytest -q`
Expected: all PASS. App boot: `PYTHONPATH=services/assistant-core/src python -c "from violet_assistant.main import create_app; from violet_assistant.config import load_settings; import pathlib; print('auto_sync' in create_app(load_settings(pathlib.Path('.').resolve())).openapi()['paths']['/api/knowledge']['get'])"` (route exists).

- [ ] **Step 6: Log + commit**

Write `logs/auto-sync-wiring_2026-07-25_log.md`, then:

```bash
git add services/assistant-core/src/violet_assistant/main.py services/assistant-core/src/violet_assistant/routes/knowledge.py services/assistant-core/tests/test_knowledge_routes.py logs/auto-sync-wiring_2026-07-25_log.md
git commit -m "feat: wire auto-sync scheduler + expose auto_sync status"
```

---

### Task 4: Frontend — Auto-sync toggle + last-sync display

**Files:**
- Modify: `apps/web-client/src/lib/api.ts` (extend `KnowledgeInfo` with `auto_sync`)
- Modify: `apps/web-client/src/components/SettingsModal.tsx` (Auto-sync toggle + last-sync per source)
- Verify: `cd apps/web-client && npm run build`

**Interfaces:**
- Consumes: `KnowledgeInfo.auto_sync`; `PATCH /api/settings` (`knowledge_auto_sync`).

- [ ] **Step 1: Extend `lib/api.ts`**

```typescript
export type AutoSyncInfo = {
  enabled: boolean;
  interval: number;
  gdrive_interval: number;
  last_sync: Record<string, { at?: string; indexed?: number; error?: string } | null>;
};

// add to KnowledgeInfo:
//   auto_sync: AutoSyncInfo;
```

- [ ] **Step 2: Auto-sync toggle in the Knowledge section (SettingsModal.tsx)**

At the top of the Knowledge base card (after the counts line), add a toggle bound to the preference:

```tsx
{knowledge.auto_sync && (
  <ToggleRow
    label="Auto-sync"
    on={knowledge.auto_sync.enabled}
    onToggle={() =>
      onPatchSettings({ knowledge_auto_sync: !knowledge.auto_sync.enabled })
    }
  />
)}
```

Note: after toggling, `onPatchSettings` refreshes `settings`; the `auto_sync.enabled` shown here comes from `knowledge` — call `onReindex`? No. Simplest: the toggle reads/writes the preference; the visible state can read from `settings?.values.knowledge_auto_sync` instead of `knowledge.auto_sync.enabled` so it updates immediately without re-fetching knowledge:

```tsx
<ToggleRow
  label="Auto-sync"
  on={values?.knowledge_auto_sync === true}
  onToggle={() =>
    onPatchSettings({ knowledge_auto_sync: !(values?.knowledge_auto_sync === true) })
  }
/>
```

Render this whenever `knowledge` is present (not gated on `auto_sync`).

- [ ] **Step 3: Last-sync display per source**

In the per-source row (from Phase C), append a last-sync hint when present:

```tsx
{knowledge.auto_sync?.last_sync?.[s.name]?.at && (
  <span className="text-steel/50">
    · synced {new Date(knowledge.auto_sync.last_sync[s.name]!.at!).toLocaleTimeString()}
  </span>
)}
```

- [ ] **Step 4: Build**

Run: `cd apps/web-client && npm run build`
Expected: clean.

- [ ] **Step 5: Log + commit**

Write `logs/auto-sync-frontend_2026-07-25_log.md`, then:

```bash
git add apps/web-client/src/lib/api.ts apps/web-client/src/components/SettingsModal.tsx logs/auto-sync-frontend_2026-07-25_log.md
git commit -m "feat: auto-sync toggle + last-sync display in knowledge UI"
```

---

## Final verification (after Task 4)
- `python -m pytest -q` → all PASS.
- App boot: `GET /api/knowledge` returns an `auto_sync` block; Drive/local off by default.
- `cd apps/web-client && npm run build` → clean.
- Manual (RAG on): enable Auto-sync in Settings; drop a file into `knowledge/`; within one interval the doc count rises with no manual click; a Drive file appears within the slower Drive interval.

## Notes for the implementer
- `run_due(now)` takes injected `now` (monotonic) for the cadence; wall-clock ISO `at` is only for display. Keep them separate so tests stay deterministic.
- The overlap guard checks `self._lock.locked()` before acquiring — the loop awaits each `run_due`, so ticks never stack from the loop itself; the guard protects against any external concurrent trigger.
- `on_event` startup/shutdown fire only under a running server, so tests exercise `run_due`/`status` directly and never start the loop.
- The auto-sync toggle reads/writes the `knowledge_auto_sync` preference via `PATCH /api/settings`; show live state from `settings.values`, not from a stale `knowledge` fetch.
