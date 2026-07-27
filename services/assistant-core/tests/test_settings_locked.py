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
