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
