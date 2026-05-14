from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from violet_assistant.llm.base import Message
from violet_assistant.memory.schema import MemoryCandidate


class SQLiteStore:
    def __init__(self, db_path: Path, migration_path: Path) -> None:
        self.db_path = db_path
        self.migration_path = migration_path

    @classmethod
    def from_database_url(
        cls, database_url: str, base_dir: Path, migration_path: Path
    ) -> "SQLiteStore":
        if not database_url.startswith("sqlite:///"):
            raise ValueError("Phase 1 only supports sqlite:/// DATABASE_URL values.")

        raw_path = database_url.removeprefix("sqlite:///")
        db_path = Path(raw_path)
        if not db_path.is_absolute():
            db_path = base_dir / db_path
        return cls(db_path=db_path, migration_path=migration_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        schema = self.migration_path.read_text(encoding="utf-8")
        with self._connect() as connection:
            connection.executescript(schema)

    def ensure_session(self, session_id: str, title: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO sessions (id, title)
                VALUES (?, ?)
                """,
                (session_id, title),
            )
            connection.execute(
                """
                UPDATE sessions
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (session_id,),
            )

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        message_id = str(uuid4())
        metadata_json = None if metadata is None else json.dumps(metadata)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO messages (id, session_id, role, content, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (message_id, session_id, role, content, metadata_json),
            )
            connection.execute(
                """
                UPDATE sessions
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (session_id,),
            )
        return message_id

    def recent_messages(self, session_id: str, limit: int = 20) -> list[Message]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content
                FROM messages
                WHERE session_id = ?
                ORDER BY rowid DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [Message(role=row["role"], content=row["content"]) for row in reversed(rows)]

    def add_memory_candidates(
        self, candidates: list[MemoryCandidate]
    ) -> None:
        if not candidates:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO memory_candidates (
                  id,
                  memory_type,
                  content,
                  reason,
                  source_message_id,
                  confidence,
                  status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        candidate.id,
                        candidate.memory_type,
                        candidate.content,
                        candidate.reason,
                        candidate.source_message_id,
                        candidate.confidence,
                        candidate.status,
                    )
                    for candidate in candidates
                ],
            )

    def pending_memory_candidates(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                  id,
                  memory_type,
                  content,
                  reason,
                  source_message_id,
                  confidence,
                  status,
                  created_at
                FROM memory_candidates
                WHERE status = 'pending'
                ORDER BY created_at DESC, rowid DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

