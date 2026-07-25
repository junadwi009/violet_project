from __future__ import annotations

import asyncio
import json
from pathlib import Path

from violet_assistant.config import Settings
from violet_assistant.llm.mock_provider import MockLLMProvider
from violet_assistant.orchestrator.chat_orchestrator import ChatOrchestrator
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.personality.loader import PersonalityLoader
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
