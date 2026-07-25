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

    def doc_by_path(self, path: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_docs WHERE path = ?", (path,)
            ).fetchone()
        return dict(row) if row else None

    def upsert_doc(self, doc_id, path, hash, mtime, chunks, model) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM knowledge_chunks WHERE doc_id = ?", (doc_id,)
            )
            connection.execute(
                """INSERT INTO knowledge_docs
                     (doc_id, path, hash, mtime, chunk_count, status, indexed_at)
                   VALUES (?, ?, ?, ?, ?, 'indexed', CURRENT_TIMESTAMP)
                   ON CONFLICT(doc_id) DO UPDATE SET
                     path=excluded.path, hash=excluded.hash, mtime=excluded.mtime,
                     chunk_count=excluded.chunk_count, status='indexed',
                     indexed_at=CURRENT_TIMESTAMP""",
                (doc_id, path, hash, mtime, len(chunks)),
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

    def list_docs(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT path, chunk_count, status, indexed_at "
                "FROM knowledge_docs ORDER BY path"
            ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict:
        with self._connect() as connection:
            docs = connection.execute(
                "SELECT COUNT(*) AS c FROM knowledge_docs"
            ).fetchone()["c"]
            chunks = connection.execute(
                "SELECT COUNT(*) AS c FROM knowledge_chunks"
            ).fetchone()["c"]
        return {"doc_count": docs, "chunk_count": chunks}
