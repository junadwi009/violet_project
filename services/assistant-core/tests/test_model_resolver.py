from __future__ import annotations

import pytest

from violet_assistant.agents.registry import AgentRegistry
from violet_assistant.config import load_settings
from violet_assistant.preferences.resolver import ModelResolver
from violet_assistant.preferences.store import PreferencesStore


@pytest.fixture()
def settings(tmp_path):
    return load_settings(tmp_path)


def test_resolve_falls_back_to_settings(tmp_path, settings):
    store = PreferencesStore(tmp_path / "preferences.json")
    resolver = ModelResolver(store, settings)
    assert resolver.resolve("persona_model") == settings.persona_model


def test_resolve_prefers_override(tmp_path, settings):
    store = PreferencesStore(tmp_path / "preferences.json")
    store.patch({"persona_model": "meta-llama/llama-3.3-70b"})
    resolver = ModelResolver(store, settings)
    assert resolver.resolve("persona_model") == "meta-llama/llama-3.3-70b"


def test_blank_override_falls_back(tmp_path, settings):
    # An emptied text field must not send model="" to the provider.
    store = PreferencesStore(tmp_path / "preferences.json")
    store.patch({"persona_model": "   "})
    resolver = ModelResolver(store, settings)
    assert resolver.resolve("persona_model") == settings.persona_model


def test_resolve_without_preferences(settings):
    assert ModelResolver(None, settings).resolve("vision_model") == settings.vision_model


def test_override_is_read_per_call(tmp_path, settings):
    # The resolver must not cache: editing prefs takes effect without a restart.
    store = PreferencesStore(tmp_path / "preferences.json")
    resolver = ModelResolver(store, settings)
    assert resolver.resolve("artifact_model") == settings.artifact_model
    store.patch({"artifact_model": "qwen/qwen3-max"})
    assert resolver.resolve("artifact_model") == "qwen/qwen3-max"


def test_agent_registry_uses_resolver_per_call(tmp_path, settings):
    agents_dir = tmp_path / "agents"
    (agents_dir / "demo").mkdir(parents=True)
    (agents_dir / "demo" / "SKILL.md").write_text(
        "---\nname: Demo\ndescription: demo agent\n---\n\nBody.\n",
        encoding="utf-8",
    )
    store = PreferencesStore(tmp_path / "preferences.json")
    resolver = ModelResolver(store, settings)
    registry = AgentRegistry(agents_dir, resolver=resolver)

    assert registry.list_agents()[0].model == settings.agent_default_model
    store.patch({"agent_default_model": "openai/gpt-oss-120b"})
    # No restart, no cache: the next call reflects the new default.
    assert registry.list_agents()[0].model == "openai/gpt-oss-120b"
