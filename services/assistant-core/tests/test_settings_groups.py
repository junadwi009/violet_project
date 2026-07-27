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
