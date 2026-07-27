from __future__ import annotations

import json
import re
import shutil
from dataclasses import fields, replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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


@pytest.mark.asyncio
async def test_export_excludes_secret_values(tmp_path, store):
    """The name-based regex above only catches secrets under expected keys.

    A leak that relabels a field — e.g. ``{"endpoint": settings.llm_base_url,
    "credential": settings.llm_api_key}`` — slides right past it while still
    putting the live value in the bundle. Give every secret-bearing
    ``Settings`` field (every ``*_api_key`` / ``*_base_url`` field) a
    distinctive canary value and assert none of those values appear anywhere
    in the serialized body, regardless of what key they might be filed
    under.
    """
    base_settings = load_settings(tmp_path)
    secret_field_names = [
        f.name
        for f in fields(base_settings)
        if f.name.endswith("_api_key") or f.name.endswith("_base_url")
    ]
    # Pinned so a newly added secret-bearing field can't silently join
    # Settings without also being covered by this loop.
    assert len(secret_field_names) == 18

    canaries = {name: f"CANARY-{name}-9f3a2b" for name in secret_field_names}
    settings = replace(base_settings, **canaries)

    prefs = PreferencesStore(tmp_path / "preferences.json")
    router = create_export_router(store, FakeMemoryStore(), prefs, settings)
    response = await _get(router)()
    body = response.body.decode("utf-8")

    for name, canary in canaries.items():
        assert canary not in body, f"secret value for {name!r} leaked into export bundle"


def test_create_app_wires_the_export_router(tmp_path):
    """Pins `app.include_router(create_export_router(...))` in `main.create_app`.

    Every other test in this file reaches the handler by walking
    `router.routes` directly (see `_get` above) — nothing exercises
    `create_app()` itself, so the `include_router(create_export_router(...))`
    call could be deleted from `main.py` and this file would stay green while
    `/api/export` silently vanished from the running app.

    repo_root is tmp_path so `create_app()` builds its `PreferencesStore` at
    a throwaway `data/preferences.json` instead of the developer's real one;
    only the migration SQL is copied in. Same isolation pattern as
    `test_model_resolver.test_create_app_wires_the_resolver`.
    """
    from violet_assistant.main import create_app

    repo_root = Path(__file__).resolve().parents[3]
    migrations = tmp_path / "database" / "migrations"
    migrations.mkdir(parents=True)
    for name in ("001_init.sql", "002_agent_runs.sql"):
        shutil.copy(repo_root / "database" / "migrations" / name, migrations / name)

    settings = replace(
        load_settings(tmp_path),
        repo_root=tmp_path,
        database_url=f"sqlite:///{tmp_path / 'violet.db'}",
        memory_dir=tmp_path / "memory",
        rag_provider="none",
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/export")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
