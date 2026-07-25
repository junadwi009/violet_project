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
        return {
            "indexed": 1, "skipped": 0, "removed": 0, "chunks": 2, "errors": [],
            "sources": {
                only: {"indexed": 1, "skipped": 0, "removed": 0, "chunks": 2, "errors": []}
            },
        }


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
