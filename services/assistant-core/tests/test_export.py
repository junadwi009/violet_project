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
