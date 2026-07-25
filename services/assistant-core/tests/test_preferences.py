from __future__ import annotations

import json

import pytest

from violet_assistant.config import load_settings
from violet_assistant.preferences.store import EDITABLE_KEYS, PreferencesStore
from violet_assistant.routes.settings import SettingsPatch, create_settings_router


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
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["temperature"] == 0.9
    # a fresh store reads the override back
    assert PreferencesStore(path).effective(settings)["temperature"] == 0.9
    assert set(PreferencesStore(path).overridden()) == {
        "temperature",
        "web_search_enabled",
    }


def test_patch_rejects_unknown_key(tmp_path):
    store = PreferencesStore(tmp_path / "preferences.json")
    with pytest.raises(ValueError):
        store.patch({"llm_api_key": "sk-nope"})


def test_patch_validates_temperature_range(tmp_path):
    store = PreferencesStore(tmp_path / "preferences.json")
    with pytest.raises(ValueError):
        store.patch({"temperature": 5.0})


def _endpoint(router, method: str):
    for route in router.routes:
        if method in route.methods:
            return route.endpoint
    raise KeyError(method)


@pytest.mark.asyncio
async def test_settings_router_roundtrip(tmp_path, settings):
    store = PreferencesStore(tmp_path / "preferences.json")
    router = create_settings_router(store, settings)

    body = await _endpoint(router, "GET")()
    assert "temperature" in body["values"]
    assert body["overridden"] == []

    patched = await _endpoint(router, "PATCH")(SettingsPatch(temperature=0.7))
    assert patched["values"]["temperature"] == 0.7
    assert "temperature" in patched["overridden"]


@pytest.mark.asyncio
async def test_settings_router_rejects_bad_value(tmp_path, settings):
    from fastapi import HTTPException

    store = PreferencesStore(tmp_path / "preferences.json")
    router = create_settings_router(store, settings)

    with pytest.raises(HTTPException) as exc_info:
        await _endpoint(router, "PATCH")(SettingsPatch(temperature=9))
    assert exc_info.value.status_code == 422
