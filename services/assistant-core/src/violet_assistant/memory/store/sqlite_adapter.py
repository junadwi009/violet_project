from __future__ import annotations

from violet_assistant.memory.store.base import MemoryRecord
from violet_assistant.persistence.sqlite_store import SQLiteStore


class SqliteApprovedMemoryStore:
    """Adapter exposing the original SQLite ``memories`` table as an ApprovedMemoryStore."""

    backend_name = "sqlite"

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def location(self) -> str:
        return str(self.store.db_path)

    def list(self) -> list[MemoryRecord]:
        return self.store.approved_memories()

    def add(
        self,
        *,
        memory_type: str,
        content: str,
        source: str,
        confidence: float,
        candidate_id: str | None = None,
    ) -> MemoryRecord:
        return self.store.insert_memory(
            memory_type=memory_type,
            content=content,
            source=source,
            confidence=confidence,
            candidate_id=candidate_id,
        )

    def update(
        self, memory_id: str, content: str, memory_type: str | None = None
    ) -> MemoryRecord:
        return self.store.update_memory(memory_id, content, memory_type)

    def delete(self, memory_id: str) -> MemoryRecord:
        return self.store.delete_memory(memory_id)
