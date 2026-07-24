from __future__ import annotations

from violet_assistant.config import Settings
from violet_assistant.memory.store.base import ApprovedMemoryStore
from violet_assistant.memory.store.file_store import FileApprovedMemoryStore
from violet_assistant.memory.store.sqlite_adapter import SqliteApprovedMemoryStore
from violet_assistant.persistence.sqlite_store import SQLiteStore


FILES = "files"
SQLITE = "sqlite"


def create_approved_memory_store(
    settings: Settings, sqlite_store: SQLiteStore
) -> ApprovedMemoryStore:
    backend = settings.memory_backend.strip().lower()
    if backend == FILES:
        return FileApprovedMemoryStore(settings.memory_dir)
    if backend == SQLITE:
        return SqliteApprovedMemoryStore(sqlite_store)
    raise ValueError(
        f"Unsupported MEMORY_BACKEND={settings.memory_backend!r}. "
        f"Supported values: {FILES}, {SQLITE} (gdrive planned)."
    )


def migrate_sqlite_memories_to_files(
    sqlite_store: SQLiteStore, file_store: FileApprovedMemoryStore
) -> int:
    """One-time, idempotent import of existing SQLite approved memories into the file store."""
    imported = 0
    for record in sqlite_store.approved_memories():
        before = file_store.import_record(record)
        if before is not None:
            imported += 1
    return imported
