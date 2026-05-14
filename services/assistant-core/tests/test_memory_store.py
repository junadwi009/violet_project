from __future__ import annotations

from pathlib import Path

import pytest

from violet_assistant.memory.schema import MemoryCandidate
from violet_assistant.persistence.sqlite_store import SQLiteStore


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = PROJECT_ROOT / "database" / "migrations" / "001_init.sql"


def _store(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore.from_database_url(
        f"sqlite:///{tmp_path / 'violet.db'}",
        base_dir=PROJECT_ROOT,
        migration_path=MIGRATION_PATH,
    )
    store.initialize()
    return store


def test_memory_candidate_approval_lifecycle(tmp_path) -> None:
    store = _store(tmp_path)
    candidate = MemoryCandidate(
        id="candidate-1",
        memory_type="profile",
        content="concise engineering updates",
        reason="User shared a preference.",
        source_message_id="message-1",
        confidence=0.8,
    )
    store.add_memory_candidates([candidate])

    updated_candidate = store.update_memory_candidate(
        "candidate-1",
        content="short engineering updates",
    )
    approval = store.approve_memory_candidate("candidate-1")
    pending = store.pending_memory_candidates()
    memories = store.approved_memories()

    assert updated_candidate["content"] == "short engineering updates"
    assert approval["status"] == "approved"
    assert pending == []
    assert len(memories) == 1
    assert memories[0]["content"] == "short engineering updates"
    assert memories[0]["approved"] == 1


def test_reject_memory_candidate_removes_from_pending(tmp_path) -> None:
    store = _store(tmp_path)
    store.add_memory_candidates(
        [
            MemoryCandidate(
                id="candidate-1",
                memory_type="profile",
                content="quiet mornings",
                reason="User shared a preference.",
                source_message_id="message-1",
                confidence=0.7,
            )
        ]
    )

    rejection = store.reject_memory_candidate("candidate-1")

    assert rejection == {"id": "candidate-1", "status": "rejected", "memory_id": None}
    assert store.pending_memory_candidates() == []
    assert store.approved_memories() == []


def test_delete_memory(tmp_path) -> None:
    store = _store(tmp_path)
    store.add_memory_candidates(
        [
            MemoryCandidate(
                id="candidate-1",
                memory_type="profile",
                content="short updates",
                reason="User shared a preference.",
                source_message_id="message-1",
                confidence=0.7,
            )
        ]
    )
    approval = store.approve_memory_candidate("candidate-1")

    result = store.delete_memory(approval["memory_id"])

    assert result["status"] == "deleted"
    assert store.approved_memories() == []


def test_missing_candidate_raises(tmp_path) -> None:
    store = _store(tmp_path)

    with pytest.raises(KeyError):
        store.approve_memory_candidate("missing")

