from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from violet_assistant.agents.registry import AgentRegistry
from violet_assistant.config import load_settings
from violet_assistant.ingestion.ocr import VisionOCR
from violet_assistant.llm.base import LLMOptions, LLMResponse, Message
from violet_assistant.orchestrator.cascade import CascadeResponder, LayerConfig
from violet_assistant.preferences.resolver import ModelResolver
from violet_assistant.preferences.store import PreferencesStore
from violet_assistant.skills.generator import SkillEngine
from violet_assistant.skills.schema import Skill


@pytest.fixture()
def settings(tmp_path):
    return load_settings(tmp_path)


class _RecordingProvider:
    """Captures the ``options.model`` of every call and replies with fixed text."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.models: list[str] = []

    async def chat(self, messages, options: LLMOptions) -> LLMResponse:
        self.models.append(options.model)
        return LLMResponse(text=self.reply, emotion="focused")

    async def health(self):  # pragma: no cover
        raise NotImplementedError


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
    # Sentinel, not the class default: AgentRegistry's own default_model happens to
    # equal settings.agent_default_model, so asserting on that would pass even if the
    # resolver were ignored. With a sentinel both assertions carry weight, and the
    # second one proves the resolver *overrides* the frozen constructor argument.
    registry = AgentRegistry(agents_dir, default_model="sentinel/frozen", resolver=resolver)

    assert registry.list_agents()[0].model == settings.agent_default_model
    store.patch({"agent_default_model": "openai/gpt-oss-120b"})
    # No restart, no cache: the next call reflects the new default.
    assert registry.list_agents()[0].model == "openai/gpt-oss-120b"


def test_resolve_rejects_unknown_key(settings):
    # A mistyped key must fail loudly at the resolver, not as a bare AttributeError
    # surfacing from getattr in the middle of a request.
    resolver = ModelResolver(None, settings)
    with pytest.raises(KeyError, match="unknown model key"):
        resolver.resolve("persona_modle")


# --- Wiring regression tests -------------------------------------------------
# Each of the following fails if its component stops consulting the resolver, or
# if main.py stops passing one in. Without them the threading is invisible to the
# suite and can be reverted silently.


def test_cascade_uses_resolver_for_persona_model(tmp_path, settings):
    prefs = PreferencesStore(tmp_path / "preferences.json")
    resolver = ModelResolver(prefs, settings)
    persona = LayerConfig("persona", "http://p", "frozen/persona", None)
    technical = LayerConfig("technical", "http://t", "frozen/technical", None)
    providers = {
        "persona": _RecordingProvider("Hello."),
        "technical": _RecordingProvider("unused"),
    }
    responder = CascadeResponder(
        persona=persona,
        technical=technical,
        provider_factory=lambda layer: providers[layer.name],
        resolver=resolver,
    )
    messages = [Message(role="system", content="sys"), Message(role="user", content="hi")]

    prefs.patch({"persona_model": "meta-llama/llama-3.3-70b"})
    result = asyncio.run(responder.respond(messages, LLMOptions(model="ignored")))

    # The model that actually reached the provider must follow the preference.
    assert providers["persona"].models == ["meta-llama/llama-3.3-70b"]
    assert result.models_used == ["meta-llama/llama-3.3-70b"]


def test_skill_engine_uses_resolver_for_artifact_model(tmp_path, settings):
    prefs = PreferencesStore(tmp_path / "preferences.json")
    resolver = ModelResolver(prefs, settings)
    provider = _RecordingProvider("```html\n<p>hi</p>\n```")
    engine = SkillEngine(provider=provider, model="frozen/artifact", resolver=resolver)
    skill = Skill(id="chart", name="Chart", kind="html", prompt="make a chart")

    prefs.patch({"artifact_model": "qwen/qwen3-max"})
    asyncio.run(engine.generate(skill, "draw something"))

    assert provider.models == ["qwen/qwen3-max"]


def test_vision_ocr_uses_resolver_for_vision_model(tmp_path, settings, monkeypatch):
    from violet_assistant.ingestion import ocr as ocr_module

    sent: list[dict] = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "text"}}]}
            ).encode("utf-8")

    def _fake_urlopen(req, timeout=None):
        sent.append(json.loads(req.data.decode("utf-8")))
        return _FakeResponse()

    monkeypatch.setattr(ocr_module.request, "urlopen", _fake_urlopen)

    prefs = PreferencesStore(tmp_path / "preferences.json")
    vision = VisionOCR(
        base_url="http://v",
        api_key="k",
        model="frozen/vision",
        resolver=ModelResolver(prefs, settings),
    )

    prefs.patch({"vision_model": "qwen/qwen3-vl-72b-instruct"})
    asyncio.run(vision.ocr(b"bytes", "image/png"))

    # The id in the request body — not just the helper's return value.
    assert sent[0]["model"] == "qwen/qwen3-vl-72b-instruct"


def test_create_app_wires_the_resolver(tmp_path, monkeypatch):
    """Pins the four ``resolver=model_resolver`` arguments in ``main.create_app``.

    repo_root is tmp_path so the app reads a throwaway ``data/preferences.json``
    instead of the developer's real one; only the migration SQL is copied in.
    """
    from violet_assistant import main as main_module

    repo_root = Path(__file__).resolve().parents[3]
    migrations = tmp_path / "database" / "migrations"
    migrations.mkdir(parents=True)
    for name in ("001_init.sql", "002_agent_runs.sql"):
        source = repo_root / "database" / "migrations" / name
        if source.exists():
            shutil.copy(source, migrations / name)

    # Every branch that holds a model id must be live for this to pin all four sites.
    settings = replace(
        load_settings(tmp_path),
        repo_root=tmp_path,
        llm_router="cascade",
        artifact_api_key="test-key",
        vision_api_key="test-key",
        rag_provider="none",
        database_url=f"sqlite:///{tmp_path / 'violet.db'}",
        memory_dir=tmp_path / "memory",
    )

    captured: dict[str, object] = {}

    def _recording(name, real):
        def factory(*args, **kwargs):
            captured[name] = kwargs.get("resolver")
            return real(*args, **kwargs)

        return factory

    for name, attr in (
        ("cascade", "CascadeResponder"),
        ("skill_engine", "SkillEngine"),
        ("agent_registry", "AgentRegistry"),
        ("vision", "VisionOCR"),
    ):
        monkeypatch.setattr(main_module, attr, _recording(name, getattr(main_module, attr)))

    main_module.create_app(settings)

    # Patched *after* the app was built: a live resolver means no restart is needed.
    prefs = PreferencesStore(tmp_path / "data" / "preferences.json")
    prefs.patch(
        {
            "persona_model": "live/persona",
            "artifact_model": "live/artifact",
            "agent_default_model": "live/agent",
            "vision_model": "live/vision",
        }
    )

    for name, key, expected in (
        ("cascade", "persona_model", "live/persona"),
        ("skill_engine", "artifact_model", "live/artifact"),
        ("agent_registry", "agent_default_model", "live/agent"),
        ("vision", "vision_model", "live/vision"),
    ):
        resolver = captured.get(name)
        assert resolver is not None, f"create_app did not pass a resolver to {name}"
        assert resolver.resolve(key) == expected
