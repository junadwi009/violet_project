from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from violet_assistant.config import Settings
from violet_assistant.llm.mock_provider import MockLLMProvider
from violet_assistant.orchestrator.chat_orchestrator import ChatOrchestrator
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.personality.loader import PersonalityLoader
from violet_assistant.preferences.resolver import ModelResolver
from violet_assistant.preferences.store import PreferencesStore
from violet_assistant.schemas.chat import ChatRequest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = PROJECT_ROOT / "database" / "migrations" / "001_init.sql"


def _write_personality(tmp_path: Path) -> Path:
    personality_dir = tmp_path / "personality"
    personality_dir.mkdir()
    (personality_dir / "violet.default.json").write_text(
        json.dumps(
            {
                "id": "violet.default",
                "name": "Violet",
                "language": "id",
                "tone": "calm",
                "verbosity": "medium",
                "style_rules": ["Be clear."],
                "safety_rules": ["Do not auto-save memory."],
            }
        ),
        encoding="utf-8",
    )
    return personality_dir


def _settings(tmp_path: Path, personality_dir: Path) -> Settings:
    return Settings(
        repo_root=PROJECT_ROOT,
        app_env="test",
        app_host="127.0.0.1",
        app_port=8000,
        public_client_url="http://localhost:3000",
        database_url=f"sqlite:///{tmp_path / 'violet.db'}",
        llm_provider="mock",
        llm_base_url="http://localhost:11434/v1",
        llm_model="mock-model",
        llm_timeout_seconds=1,
        llm_api_key=None,
        personality_config_dir=personality_dir,
        rag_provider="none",
        memory_backend="sqlite",
        memory_dir=tmp_path / "memory",
        memory_auto_save=False,
        memory_require_approval=True,
        log_level="debug",
    )


def test_chat_orchestrator_persists_messages_and_candidates(tmp_path) -> None:
    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    store = SQLiteStore.from_database_url(
        settings.database_url,
        base_dir=settings.repo_root,
        migration_path=MIGRATION_PATH,
    )
    store.initialize()
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=MockLLMProvider(),
        personality_loader=PersonalityLoader(personality_dir),
        store=store,
    )

    response = asyncio.run(
        orchestrator.chat(
            ChatRequest(
                content="Remember that I prefer short implementation notes.",
                personality_id="violet.default",
            )
        )
    )

    messages = store.recent_messages(response.session_id)
    pending_candidates = store.pending_memory_candidates()

    assert response.text.startswith("Violet mock response")
    assert [message.role for message in messages] == ["user", "assistant"]
    assert len(response.memory_candidates) == 1
    assert len(pending_candidates) == 1
    assert pending_candidates[0]["status"] == "pending"


class _FakeSkillEngine:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(self, skill, content):
        self.calls.append(skill.id)
        return (
            "here is your artifact",
            [
                {
                    "id": "art-1",
                    "kind": "html",
                    "title": "T",
                    "spec": None,
                    "html": "<p>hi</p>",
                    "file_base64": None,
                    "filename": None,
                    "mime": None,
                }
            ],
        )


class _FakeWebProvider:
    name = "web"

    def _request_json(self, method, path, payload):
        assert payload["model"].endswith(":online")
        return {
            "choices": [
                {
                    "message": {
                        "content": "web says hi",
                        "annotations": [
                            {"type": "url_citation", "url_citation": {"url": "https://src"}}
                        ],
                    }
                }
            ]
        }

    async def chat(self, messages, options):  # pragma: no cover - unused
        raise NotImplementedError

    async def health(self):  # pragma: no cover - unused
        raise NotImplementedError


def _store(settings):
    store = SQLiteStore.from_database_url(
        settings.database_url,
        base_dir=settings.repo_root,
        migration_path=MIGRATION_PATH,
    )
    store.initialize()
    return store


def _chart_skill_dir(tmp_path: Path) -> Path:
    d = tmp_path / "skills"
    d.mkdir(exist_ok=True)
    (d / "chart.json").write_text(
        json.dumps(
            {"id": "chart", "name": "Chart", "kind": "chartjs", "triggers": ["chart"], "prompt": "p"}
        ),
        encoding="utf-8",
    )
    return d


def test_explicit_skill_id_forces_that_skill(tmp_path) -> None:
    from violet_assistant.skills.registry import SkillRegistry

    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    engine = _FakeSkillEngine()
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=MockLLMProvider(),
        personality_loader=PersonalityLoader(personality_dir),
        store=_store(settings),
        skill_registry=SkillRegistry(_chart_skill_dir(tmp_path)),
        skill_engine=engine,
    )

    response = asyncio.run(
        orchestrator.chat(
            ChatRequest(
                content="please build me something",  # no trigger word
                personality_id="violet.default",
                skill_id="chart",
            )
        )
    )

    assert engine.calls == ["chart"]
    assert response.text == "here is your artifact"
    assert len(response.artifacts) == 1
    assert response.artifacts[0].kind == "html"


def test_web_search_routes_through_web_provider(tmp_path) -> None:
    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=MockLLMProvider(),
        personality_loader=PersonalityLoader(personality_dir),
        store=_store(settings),
        web_provider=_FakeWebProvider(),
    )

    response = asyncio.run(
        orchestrator.chat(
            ChatRequest(
                content="what is the latest news?",
                personality_id="violet.default",
                web_search=True,
            )
        )
    )

    assert response.text == "web says hi"
    assert response.citations == ["https://src"]


class _StubProvider:
    name = "stub"

    async def chat(self, messages, options):
        from violet_assistant.llm.base import LLMResponse

        return LLMResponse(text="answer", emotion="focused")

    async def health(self):  # pragma: no cover
        raise NotImplementedError


class _FakeRetriever:
    name = "vector"

    async def retrieve(self, query, k=4):
        from violet_assistant.rag.base import Chunk

        return [Chunk(text="context", source="notes.md", score=0.9)]


def test_retrieved_sources_become_citations(tmp_path) -> None:
    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=_StubProvider(),
        personality_loader=PersonalityLoader(personality_dir),
        store=_store(settings),
        retriever=_FakeRetriever(),
    )

    response = asyncio.run(
        orchestrator.chat(
            ChatRequest(content="tell me about the notes", personality_id="violet.default")
        )
    )

    assert response.text == "answer"
    assert response.citations == ["notes.md"]


def test_skill_response_does_not_carry_retrieved_citations(tmp_path) -> None:
    """A skill/artifact answer never sees the retrieved context, so it must not cite it."""
    from violet_assistant.skills.registry import SkillRegistry

    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=_StubProvider(),
        personality_loader=PersonalityLoader(personality_dir),
        store=_store(settings),
        retriever=_FakeRetriever(),  # would supply "notes.md"
        skill_registry=SkillRegistry(_chart_skill_dir(tmp_path)),
        skill_engine=_FakeSkillEngine(),
    )

    response = asyncio.run(
        orchestrator.chat(
            ChatRequest(
                content="plot this",
                personality_id="violet.default",
                skill_id="chart",
            )
        )
    )

    assert len(response.artifacts) == 1
    assert response.citations == []


def test_auto_detected_skill_also_drops_citations(tmp_path) -> None:
    from violet_assistant.skills.registry import SkillRegistry

    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=_StubProvider(),
        personality_loader=PersonalityLoader(personality_dir),
        store=_store(settings),
        retriever=_FakeRetriever(),
        skill_registry=SkillRegistry(_chart_skill_dir(tmp_path)),
        skill_engine=_FakeSkillEngine(),
    )

    response = asyncio.run(
        orchestrator.chat(
            ChatRequest(content="make me a chart", personality_id="violet.default")
        )
    )

    assert len(response.artifacts) == 1
    assert response.citations == []


def test_non_skill_answer_keeps_retrieved_citations(tmp_path) -> None:
    """Guard: the normal path must still cite retrieved sources."""
    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=_StubProvider(),
        personality_loader=PersonalityLoader(personality_dir),
        store=_store(settings),
        retriever=_FakeRetriever(),
    )
    response = asyncio.run(
        orchestrator.chat(
            ChatRequest(content="tell me about the notes", personality_id="violet.default")
        )
    )
    assert response.citations == ["notes.md"]


class _StubLoop:
    """Returns a paused outcome so we can assert the orchestrator persists + surfaces it."""

    def __init__(self, status="awaiting_approval"):
        self.status = status

    async def run(self, agent, history):
        from violet_assistant.agents.loop import LoopOutcome

        return LoopOutcome(
            status=self.status,
            text="need approval",
            trace=[{"tool": "fetch_url", "args": "url=https://x",
                    "status": "awaiting_approval", "summary": "needs your approval"}],
            citations=[],
            artifacts=[],
            pending=[{"id": "c1", "tool": "fetch_url", "arguments": {"url": "https://x"},
                      "risk": "medium", "description": "fetch"}],
            messages=[],
            iterations=1,
        )


class _OneAgentRegistry:
    def __init__(self, agent):
        self._agent = agent

    def get(self, agent_id):
        return self._agent if agent_id == self._agent.id else None

    def detect(self, text):
        return None

    def list_agents(self):
        return [self._agent]


def test_agent_loop_pause_surfaces_tool_requests_and_run_id(tmp_path) -> None:
    from dataclasses import replace

    from violet_assistant.agents.schema import Agent

    personality_dir = _write_personality(tmp_path)
    settings = replace(_settings(tmp_path, personality_dir), agent_tools_enabled=True)
    store = _store(settings)
    agent = Agent(id="researcher", name="Researcher", model="m", system_prompt="sys")

    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=_StubProvider(),
        personality_loader=PersonalityLoader(personality_dir),
        store=store,
        agent_registry=_OneAgentRegistry(agent),
        agent_runner=object(),   # present but unused: the loop takes precedence
    )
    orchestrator.agent_loop = _StubLoop()

    response = asyncio.run(
        orchestrator.chat(
            ChatRequest(content="look this up", personality_id="violet.default",
                        agent="researcher")
        )
    )

    assert response.agent_run_id is not None
    assert response.tool_requests[0]["tool"] == "fetch_url"
    assert response.tool_trace[0]["status"] == "awaiting_approval"
    assert store.get_agent_run(response.agent_run_id)["status"] == "awaiting_approval"


# --- Blank-override guard for the two model keys not routed through ModelResolver
# directly (task 13 review finding) ------------------------------------------------
#
# `llm_model` and `web_search_model` are resolved inline in chat_orchestrator.py
# rather than by calling ModelResolver.resolve() at the call site the way the other
# five model keys are (cascade, skill engine, agent registry, vision OCR). These
# mirror test_blank_override_falls_back in test_model_resolver.py, but assert on the
# value that actually reaches the provider/request payload — not just what a helper
# returns — since that is what silently regressed here before.


class _RecordingProvider:
    """Captures every ``options.model`` passed to ``chat()``."""

    name = "stub"

    def __init__(self, reply: str = "ok") -> None:
        self._reply = reply
        self.models: list[str] = []

    async def chat(self, messages, options):
        from violet_assistant.llm.base import LLMResponse

        self.models.append(options.model)
        return LLMResponse(text=self._reply, emotion="focused")

    async def health(self):  # pragma: no cover
        raise NotImplementedError


class _RecordingWebProvider:
    """Like ``_FakeWebProvider`` but records the exact model id sent, not just its
    ``:online`` suffix — ``"" + ":online"`` also ends with ``:online``, so a suffix
    check alone would not catch a blank override reaching the request payload."""

    name = "web"

    def __init__(self) -> None:
        self.models: list[str] = []

    def _request_json(self, method, path, payload):
        self.models.append(payload["model"])
        return {"choices": [{"message": {"content": "web says hi", "annotations": []}}]}

    async def chat(self, messages, options):  # pragma: no cover - unused
        raise NotImplementedError

    async def health(self):  # pragma: no cover - unused
        raise NotImplementedError


@pytest.mark.parametrize("blank", ["", "   "])
def test_llm_model_blank_override_falls_back_to_settings(tmp_path, blank) -> None:
    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    prefs = PreferencesStore(tmp_path / "preferences.json")
    prefs.patch({"llm_model": blank})
    provider = _RecordingProvider()
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=provider,
        personality_loader=PersonalityLoader(personality_dir),
        store=_store(settings),
        preferences=prefs,
        resolver=ModelResolver(prefs, settings),
    )

    asyncio.run(
        orchestrator.chat(ChatRequest(content="hello", personality_id="violet.default"))
    )

    # The model that actually reached the provider must be the Settings default,
    # not the blanked-out override — a bare dict.get(..., default) never applies
    # this fallback because _defaults() always seeds the key.
    assert provider.models == [settings.llm_model]


@pytest.mark.parametrize("blank", ["", "   "])
def test_web_search_model_blank_override_falls_back_to_settings(tmp_path, blank) -> None:
    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    prefs = PreferencesStore(tmp_path / "preferences.json")
    prefs.patch({"web_search_model": blank})
    web_provider = _RecordingWebProvider()
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=MockLLMProvider(),
        personality_loader=PersonalityLoader(personality_dir),
        store=_store(settings),
        preferences=prefs,
        web_provider=web_provider,
        resolver=ModelResolver(prefs, settings),
    )

    asyncio.run(
        orchestrator.chat(
            ChatRequest(
                content="what is the latest news?",
                personality_id="violet.default",
                web_search=True,
            )
        )
    )

    # The observable failure this guards against: a blank web_search_model must
    # never reach web_answer() as "", which web/search.py turns into ":online".
    assert web_provider.models == [f"{settings.web_search_model}:online"]
    assert ":online" not in web_provider.models
