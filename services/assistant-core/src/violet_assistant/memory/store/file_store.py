from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from violet_assistant.memory.store.base import MemoryRecord


_FRONTMATTER_KEYS = (
    "id",
    "memory_type",
    "source",
    "confidence",
    "created_at",
    "updated_at",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return (slug[:40].strip("-")) or "memory"


def _one_line(text: str, limit: int = 100) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


class FileApprovedMemoryStore:
    """Approved memories as markdown files: ``<dir>/memories/<slug>--<id>.md`` + ``MEMORY.md`` index.

    Human-editable and directory-portable — point ``MEMORY_DIR`` at a local folder, a VPS mount,
    or a Google-Drive-synced folder and the files sync with it.
    """

    backend_name = "files"

    def __init__(self, memory_dir: Path) -> None:
        self.memory_dir = Path(memory_dir)
        self.entries_dir = self.memory_dir / "memories"
        self.index_path = self.memory_dir / "MEMORY.md"
        self.entries_dir.mkdir(parents=True, exist_ok=True)

    def location(self) -> str:
        return str(self.memory_dir)

    # ---- reads -------------------------------------------------------------
    def list(self) -> list[MemoryRecord]:
        records = [record for _, record in self._read_all()]
        records.sort(key=lambda r: (r.get("updated_at") or "", r["id"]), reverse=True)
        return records

    # ---- writes ------------------------------------------------------------
    def add(
        self,
        *,
        memory_type: str,
        content: str,
        source: str,
        confidence: float,
        candidate_id: str | None = None,
    ) -> MemoryRecord:
        now = _now()
        record: MemoryRecord = {
            "id": str(uuid4()),
            "memory_type": memory_type,
            "content": content.strip(),
            "source": source,
            "confidence": float(confidence),
            "approved": 1,
            "created_at": now,
            "updated_at": now,
        }
        self._write_record(record)
        self._rebuild_index()
        return record

    def import_record(self, record: MemoryRecord) -> MemoryRecord | None:
        """Write a pre-existing record (id/dates preserved) for migration. Idempotent.

        Returns the written record, or ``None`` if a memory with that id already exists.
        """
        if self._path_for(record["id"]) is not None:
            return None
        normalized = {
            "id": record["id"],
            "memory_type": record.get("memory_type", "profile"),
            "content": (record.get("content") or "").strip(),
            "source": record.get("source", "unknown"),
            "confidence": float(record.get("confidence", 0.5)),
            "approved": 1,
            "created_at": record.get("created_at") or _now(),
            "updated_at": record.get("updated_at") or _now(),
        }
        self._write_record(normalized)
        self._rebuild_index()
        return normalized

    def update(
        self, memory_id: str, content: str, memory_type: str | None = None
    ) -> MemoryRecord:
        path = self._path_for(memory_id)
        if path is None:
            raise KeyError(memory_id)
        record = self._parse(path)
        record["content"] = content.strip()
        if memory_type is not None:
            record["memory_type"] = memory_type
        record["updated_at"] = _now()
        # Filename is keyed by id and stays stable across content edits.
        path.write_text(self._render(record), encoding="utf-8")
        self._rebuild_index()
        return record

    def delete(self, memory_id: str) -> MemoryRecord:
        path = self._path_for(memory_id)
        if path is None:
            raise KeyError(memory_id)
        path.unlink()
        self._rebuild_index()
        return {"id": memory_id, "status": "deleted", "memory_id": memory_id}

    # ---- internals ---------------------------------------------------------
    def _path_for(self, memory_id: str) -> Path | None:
        for path, record in self._read_all():
            if record["id"] == memory_id:
                return path
        return None

    def _write_record(self, record: MemoryRecord) -> None:
        filename = f"{_slug(record['content'])}--{record['id']}.md"
        (self.entries_dir / filename).write_text(self._render(record), encoding="utf-8")

    def _read_all(self) -> list[tuple[Path, MemoryRecord]]:
        results: list[tuple[Path, MemoryRecord]] = []
        if not self.entries_dir.exists():
            return results
        for path in sorted(self.entries_dir.glob("*.md")):
            try:
                results.append((path, self._parse(path)))
            except (ValueError, KeyError):
                continue  # skip malformed files rather than crash
        return results

    @staticmethod
    def _render(record: MemoryRecord) -> str:
        lines = ["---"]
        for key in _FRONTMATTER_KEYS:
            lines.append(f"{key}: {record[key]}")
        lines.append("---")
        lines.append("")
        lines.append(record["content"].strip())
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _parse(path: Path) -> MemoryRecord:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            raise ValueError("missing frontmatter")
        _, frontmatter, body = text.split("---", 2)
        meta: dict[str, str] = {}
        for line in frontmatter.strip().splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip()
        return {
            "id": meta["id"],
            "memory_type": meta.get("memory_type", "profile"),
            "content": body.strip(),
            "source": meta.get("source", "unknown"),
            "confidence": float(meta.get("confidence", "0.5")),
            "approved": 1,
            "created_at": meta.get("created_at", ""),
            "updated_at": meta.get("updated_at", ""),
        }

    def _rebuild_index(self) -> None:
        records = self.list()
        lines = [
            "# Violet Memory",
            "",
            f"_{len(records)} approved "
            f"{'memory' if len(records) == 1 else 'memories'}. "
            "Managed as markdown files in this directory — edit or delete freely._",
            "",
        ]
        for record in records:
            filename = f"{_slug(record['content'])}--{record['id']}.md"
            lines.append(
                f"- **{record['memory_type']}** — {_one_line(record['content'])} "
                f"([{filename}](memories/{filename}))"
            )
        lines.append("")
        self.index_path.write_text("\n".join(lines), encoding="utf-8")
