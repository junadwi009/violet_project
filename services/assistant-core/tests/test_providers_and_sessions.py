from __future__ import annotations

import asyncio
import json
from pathlib import Path

from violet_assistant.config import Settings
from violet_assistant.llm.base import LLMOptions, LLMResponse, Message
from violet_assistant.llm.mock_provider import MockLLMProvider
from violet_assistant.llm.registry import (
    build_provider_registry,
    default_provider_name,
    describe_providers,
)
from violet_assistant.orchestrator.chat_orchestrator import ChatOrchestrator
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.personality.loader import PersonalityLoader
from violet_assistant.schemas.chat import ChatRequest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = PROJECT_ROOT / "database" / "migrations" / "001_init.sql"


class MarkerProvider:
    """Provider that returns an identifiable marker so we can prove selection."""

    name = "marker"

    async def chat(self, messages, options: LLMOptions) -> LLMResponse:
        return LLMResponse(text="MARKER-PROVIDER-USED", emotion="focused")

    async def health(self):  # pragma: no cover
        raise NotImplementedError


def _write_personality(tmp_path: Path) -> Path:
    personality_dir = tmp_path / "personality"
    personality_dir.mkdir()
    (personality_dir / "violet.default.json").write_text(
        json.dumps({"id": "violet.default", "name": "Violet"}),
        encoding="utf-8",
    )
    return personality_dir


def _settings(tmp_path: Path, personality_dir: Path, llm_provider: str = "mock") -> Settings:
    return Settings(
        repo_root=PROJECT_ROOT,
        app_env="test",
        app_host="127.0.0.1",
        app_port=8000,
        public_client_url="http://localhost:3000",
        database_url=f"sqlite:///{tmp_path / 'violet.db'}",
        llm_provider=llm_provider,
        llm_base_url="http://localhost:11434/v1",
        llm_model="mock-model",
        llm_timeout_seconds=1,
        llm_api_key=None,
        personality_config_dir=personality_dir,
        rag_provider="none",
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


def test_registry_exposes_mock_and_openai_compatible(tmp_path) -> None:
    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    registry = build_provider_registry(settings)
    assert set(registry) == {"mock", "openai_compatible"}


def test_default_provider_name_tracks_config(tmp_path) -> None:
    personality_dir = _write_personality(tmp_path)
    assert default_provider_name(_settings(tmp_path, personality_dir, "mock")) == "mock"
    assert (
        default_provider_name(_settings(tmp_path, personality_dir, "ollama"))
        == "openai_compatible"
    )


def test_describe_providers_marks_active(tmp_path) -> None:
    personality_dir = _write_personality(tmp_path)
    payload = describe_providers(_settings(tmp_path, personality_dir, "mock"))
    assert payload["active"] == "mock"
    active_ids = [item["id"] for item in payload["items"] if item["active"]]
    assert active_ids == ["mock"]


def test_orchestrator_selects_requested_provider(tmp_path) -> None:
    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=MockLLMProvider(),
        personality_loader=PersonalityLoader(personality_dir),
        store=_store(settings),
        provider_registry={"marker": MarkerProvider()},
    )

    response = asyncio.run(
        orchestrator.chat(ChatRequest(content="Hi", provider="marker"))
    )
    assert response.text == "MARKER-PROVIDER-USED"


def test_orchestrator_falls_back_to_default_for_unknown_provider(tmp_path) -> None:
    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=MockLLMProvider(),
        personality_loader=PersonalityLoader(personality_dir),
        store=_store(settings),
        provider_registry={"marker": MarkerProvider()},
    )

    response = asyncio.run(
        orchestrator.chat(ChatRequest(content="Hi", provider="does-not-exist"))
    )
    assert response.text.startswith("Violet mock response")


def test_sessions_listing_and_message_reload(tmp_path) -> None:
    personality_dir = _write_personality(tmp_path)
    settings = _settings(tmp_path, personality_dir)
    store = _store(settings)
    orchestrator = ChatOrchestrator(
        settings=settings,
        provider=MockLLMProvider(),
        personality_loader=PersonalityLoader(personality_dir),
        store=store,
    )

    first = asyncio.run(orchestrator.chat(ChatRequest(content="First message")))

    listed = store.list_sessions()
    assert len(listed) == 1
    assert listed[0]["id"] == first.session_id
    assert listed[0]["message_count"] == 2  # user + assistant

    history = store.messages_for_session(first.session_id)
    assert [row["role"] for row in history] == ["user", "assistant"]
    assert history[0]["content"] == "First message"
