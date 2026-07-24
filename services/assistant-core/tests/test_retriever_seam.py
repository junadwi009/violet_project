from __future__ import annotations

import asyncio
import json
from pathlib import Path

from violet_assistant.config import Settings
from violet_assistant.llm.base import LLMOptions, LLMResponse, Message
from violet_assistant.orchestrator.chat_orchestrator import ChatOrchestrator
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.personality.loader import PersonalityLoader
from violet_assistant.rag.base import Chunk
from violet_assistant.rag.factory import create_retriever
from violet_assistant.rag.no_op_retriever import NoOpRetriever
from violet_assistant.schemas.chat import ChatRequest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = PROJECT_ROOT / "database" / "migrations" / "001_init.sql"


class RecordingProvider:
    name = "recording"

    def __init__(self) -> None:
        self.last_messages: list[Message] = []

    async def chat(self, messages, options: LLMOptions) -> LLMResponse:
        self.last_messages = list(messages)
        return LLMResponse(text="ok", emotion="neutral")

    async def health(self):  # pragma: no cover - not exercised here
        raise NotImplementedError


class StubRetriever:
    name = "stub"

    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        self.queries: list[str] = []

    async def retrieve(self, query: str, k: int = 4) -> list[Chunk]:
        self.queries.append(query)
        return self._chunks


def _write_personality(tmp_path: Path) -> Path:
    personality_dir = tmp_path / "personality"
    personality_dir.mkdir()
    (personality_dir / "violet.default.json").write_text(
        json.dumps({"id": "violet.default", "name": "Violet"}),
        encoding="utf-8",
    )
    return personality_dir


def _settings(tmp_path: Path, personality_dir: Path, rag_provider: str = "none") -> Settings:
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
        rag_provider=rag_provider,
        memory_backend="sqlite",
        memory_dir=tmp_path / "memory",
        memory_auto_save=False,
        memory_require_approval=True,
        log_level="debug",
    )


def _store(settings: Settings) -> SQLiteStore:
    store = SQLiteStore.from_database_url(
        settings.database_url,
        base_dir=settings.repo_root,
        migration_path=MIGRATION_PATH,
    )
    store.initialize()
    return store


def test_factory_defaults_to_no_op(tmp_path) -> None:
    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir, rag_provider="none")
    retriever = create_retriever(settings)
    assert isinstance(retriever, NoOpRetriever)
    assert asyncio.run(retriever.retrieve("anything")) == []


def test_no_op_retriever_leaves_system_prompt_clean(tmp_path) -> None:
    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    provider = RecordingProvider()
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=provider,
        personality_loader=PersonalityLoader(personality_dir),
        store=_store(settings),
        retriever=NoOpRetriever(),
    )

    asyncio.run(orchestrator.chat(ChatRequest(content="Hello there")))

    system_message = provider.last_messages[0]
    assert system_message.role == "system"
    assert "Retrieved context" not in system_message.content


def test_retrieved_chunks_are_injected_into_system_prompt(tmp_path) -> None:
    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    provider = RecordingProvider()
    retriever = StubRetriever(
        [
            Chunk(text="Violet ships local-first.", source="doc:readme", score=0.9),
            Chunk(text="Memory is approval-gated.", source="doc:claude", score=0.8),
        ]
    )
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=provider,
        personality_loader=PersonalityLoader(personality_dir),
        store=_store(settings),
        retriever=retriever,
    )

    asyncio.run(orchestrator.chat(ChatRequest(content="What is Violet?")))

    system_content = provider.last_messages[0].content
    assert "Retrieved context" in system_content
    assert "Violet ships local-first." in system_content
    assert "Memory is approval-gated." in system_content
    assert retriever.queries == ["What is Violet?"]


def test_orchestrator_defaults_retriever_to_no_op(tmp_path) -> None:
    """Backward compatibility: omitting retriever must not change behavior."""
    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    provider = RecordingProvider()
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=provider,
        personality_loader=PersonalityLoader(personality_dir),
        store=_store(settings),
    )

    asyncio.run(orchestrator.chat(ChatRequest(content="Hi")))

    assert "Retrieved context" not in provider.last_messages[0].content
