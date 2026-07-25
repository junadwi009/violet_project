from __future__ import annotations

import math
import sqlite3
from array import array
from pathlib import Path
from uuid import uuid4

_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_docs (
  doc_id TEXT PRIMARY KEY,
  path TEXT UNIQUE,
  hash TEXT,
  version TEXT,
  origin TEXT DEFAULT 'local',
  mtime REAL,
  chunk_count INTEGER,
  status TEXT,
  indexed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS knowledge_chunks (
  id TEXT PRIMARY KEY,
  doc_id TEXT,
  source TEXT,
  chunk_index INTEGER,
  text TEXT,
  embedding BLOB,
  model TEXT,
  dim INTEGER
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON knowledge_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_model ON knowledge_chunks(model);
"""


def _to_blob(vector: list[float]) -> bytes:
    return array("f", vector).tobytes()


def _from_blob(blob: bytes) -> list[float]:
    arr = array("f")
    arr.frombytes(blob)
    return list(arr)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class SqliteVectorStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            self._migrate(connection)

    def _migrate(self, connection) -> None:
        cols = {row["name"] for row in connection.execute("PRAGMA table_info(knowledge_docs)")}
        if "version" not in cols:
            connection.execute("ALTER TABLE knowledge_docs ADD COLUMN version TEXT")
            connection.execute(
                "UPDATE knowledge_docs SET version = hash WHERE version IS NULL"
            )
        if "origin" not in cols:
            connection.execute(
                "ALTER TABLE knowledge_docs ADD COLUMN origin TEXT DEFAULT 'local'"
            )
            connection.execute(
                "UPDATE knowledge_docs SET origin = 'local' WHERE origin IS NULL"
            )

    def doc_by_path(self, path: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_docs WHERE path = ?", (path,)
            ).fetchone()
        return dict(row) if row else None

    def doc_by_id(self, doc_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_docs WHERE doc_id = ?", (doc_id,)
            ).fetchone()
        return dict(row) if row else None

    def delete_missing(self, origin: str, seen_ids: set[str]) -> int:
        removed = 0
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT doc_id FROM knowledge_docs WHERE origin = ?", (origin,)
            ).fetchall()
            for row in rows:
                if row["doc_id"] not in seen_ids:
                    connection.execute(
                        "DELETE FROM knowledge_chunks WHERE doc_id = ?", (row["doc_id"],)
                    )
                    connection.execute(
                        "DELETE FROM knowledge_docs WHERE doc_id = ?", (row["doc_id"],)
                    )
                    removed += 1
        return removed

    def upsert_doc(self, doc_id, path, version, mtime, chunks, model, origin="local") -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM knowledge_chunks WHERE doc_id = ?", (doc_id,)
            )
            connection.execute(
                """INSERT INTO knowledge_docs
                     (doc_id, path, hash, version, origin, mtime, chunk_count, status, indexed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'indexed', CURRENT_TIMESTAMP)
                   ON CONFLICT(doc_id) DO UPDATE SET
                     path=excluded.path, hash=excluded.hash, version=excluded.version,
                     origin=excluded.origin, mtime=excluded.mtime,
                     chunk_count=excluded.chunk_count, status='indexed',
                     indexed_at=CURRENT_TIMESTAMP""",
                (doc_id, path, version, version, origin, mtime, len(chunks)),
            )
            for index, (text, vector) in enumerate(chunks):
                connection.execute(
                    """INSERT INTO knowledge_chunks
                         (id, doc_id, source, chunk_index, text, embedding, model, dim)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid4()),
                        doc_id,
                        path,
                        index,
                        text,
                        _to_blob(vector),
                        model,
                        len(vector),
                    ),
                )

    def query(self, vector, k, model) -> list[dict]:
        dim = len(vector)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT text, source, chunk_index, embedding "
                "FROM knowledge_chunks WHERE model = ? AND dim = ?",
                (model, dim),
            ).fetchall()
        scored = [
            {
                "text": row["text"],
                "source": row["source"],
                "chunk_index": row["chunk_index"],
                "score": _cosine(vector, _from_blob(row["embedding"])),
            }
            for row in rows
        ]
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:k]

    def delete_doc(self, doc_id) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM knowledge_chunks WHERE doc_id = ?", (doc_id,)
            )
            connection.execute("DELETE FROM knowledge_docs WHERE doc_id = ?", (doc_id,))

    def list_docs(self, origin: str | None = None) -> list[dict]:
        query = "SELECT path, chunk_count, status, indexed_at, origin FROM knowledge_docs"
        params: tuple = ()
        if origin is not None:
            query += " WHERE origin = ?"
            params = (origin,)
        query += " ORDER BY path"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def stats(self, origin: str | None = None) -> dict:
        with self._connect() as connection:
            if origin is None:
                docs = connection.execute(
                    "SELECT COUNT(*) AS c FROM knowledge_docs"
                ).fetchone()["c"]
                chunks = connection.execute(
                    "SELECT COUNT(*) AS c FROM knowledge_chunks"
                ).fetchone()["c"]
            else:
                docs = connection.execute(
                    "SELECT COUNT(*) AS c FROM knowledge_docs WHERE origin = ?", (origin,)
                ).fetchone()["c"]
                chunks = connection.execute(
                    "SELECT COUNT(*) AS c FROM knowledge_chunks WHERE doc_id IN "
                    "(SELECT doc_id FROM knowledge_docs WHERE origin = ?)",
                    (origin,),
                ).fetchone()["c"]
        return {"doc_count": docs, "chunk_count": chunks}
