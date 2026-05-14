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
