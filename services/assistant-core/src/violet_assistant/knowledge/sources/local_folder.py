from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from violet_assistant.knowledge.sources.base import SourceDocument

_SUPPORTED = {
    ".txt", ".md", ".markdown", ".log", ".rst",
    ".csv", ".tsv", ".xlsx", ".xlsm", ".pdf", ".docx", ".json",
}


class LocalFolderSource:
    name = "local"

    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = Path(knowledge_dir)

    def status(self) -> dict:
        exists = self.knowledge_dir.exists()
        return {
            "name": "local",
            "connected": exists,
            "detail": "ok" if exists else "folder_missing",
            "folder": str(self.knowledge_dir),
        }

    def list_documents(self) -> Iterable[SourceDocument]:
        if not self.knowledge_dir.exists():
            return
        for path in sorted(self.knowledge_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _SUPPORTED:
                continue
            rel = str(path.relative_to(self.knowledge_dir).as_posix())
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            yield SourceDocument(
                doc_id=f"local:{rel}",
                display_path=rel,
                version=digest,
                filename=path.name,
            )

    def read(self, doc: SourceDocument) -> bytes:
        rel = doc.doc_id.split("local:", 1)[1]
        return (self.knowledge_dir / rel).read_bytes()
