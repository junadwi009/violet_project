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

    def approved_memories(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                  id,
                  memory_type,
                  content,
                  source,
                  confidence,
                  approved,
                  metadata_json,
                  created_at,
                  updated_at
                FROM memories
                WHERE approved = 1
                ORDER BY updated_at DESC, rowid DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def update_memory_candidate(
        self, candidate_id: str, content: str, memory_type: str | None = None
    ) -> dict[str, Any]:
        with self._connect() as connection:
            existing = self._candidate_row(connection, candidate_id)
            if existing is None:
                raise KeyError(candidate_id)
            connection.execute(
                """
                UPDATE memory_candidates
                SET content = ?, memory_type = COALESCE(?, memory_type)
                WHERE id = ? AND status = 'pending'
                """,
                (content, memory_type, candidate_id),
            )
            updated = self._candidate_row(connection, candidate_id)
        if updated is None:
            raise KeyError(candidate_id)
        return dict(updated)

    def approve_memory_candidate(self, candidate_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            candidate = self._candidate_row(connection, candidate_id)
            if candidate is None or candidate["status"] != "pending":
                raise KeyError(candidate_id)

            memory_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO memories (
                  id,
                  memory_type,
                  content,
                  source,
                  confidence,
                  approved,
                  metadata_json
                )
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    memory_id,
                    candidate["memory_type"],
                    candidate["content"],
                    f"message:{candidate['source_message_id']}",
                    candidate["confidence"],
                    json.dumps({"candidate_id": candidate_id}),
                ),
            )
            connection.execute(
                """
                UPDATE memory_candidates
                SET status = 'approved'
                WHERE id = ?
                """,
                (candidate_id,),
            )
        return {"id": candidate_id, "status": "approved", "memory_id": memory_id}

    def reject_memory_candidate(self, candidate_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            candidate = self._candidate_row(connection, candidate_id)
            if candidate is None or candidate["status"] != "pending":
                raise KeyError(candidate_id)
            connection.execute(
                """
                UPDATE memory_candidates
                SET status = 'rejected'
                WHERE id = ?
                """,
                (candidate_id,),
            )
        return {"id": candidate_id, "status": "rejected", "memory_id": None}

    def update_memory(
        self, memory_id: str, content: str, memory_type: str | None = None
    ) -> dict[str, Any]:
        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT id
                FROM memories
                WHERE id = ? AND approved = 1
                """,
                (memory_id,),
            ).fetchone()
            if existing is None:
                raise KeyError(memory_id)
            connection.execute(
                """
                UPDATE memories
                SET content = ?,
                    memory_type = COALESCE(?, memory_type),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (content, memory_type, memory_id),
            )
            row = connection.execute(
                """
                SELECT
                  id,
                  memory_type,
                  content,
                  source,
                  confidence,
                  approved,
                  metadata_json,
                  created_at,
                  updated_at
                FROM memories
                WHERE id = ?
                """,
                (memory_id,),
            ).fetchone()
        if row is None:
            raise KeyError(memory_id)
        return dict(row)

    def delete_memory(self, memory_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            result = connection.execute(
                """
                DELETE FROM memories
                WHERE id = ?
                """,
                (memory_id,),
            )
            if result.rowcount == 0:
                raise KeyError(memory_id)
        return {"id": memory_id, "status": "deleted", "memory_id": memory_id}

    def _candidate_row(
        self, connection: sqlite3.Connection, candidate_id: str
    ) -> sqlite3.Row | None:
        return connection.execute(
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
            WHERE id = ?
            """,
            (candidate_id,),
        ).fetchone()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
