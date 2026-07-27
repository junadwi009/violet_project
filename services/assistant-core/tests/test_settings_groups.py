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
