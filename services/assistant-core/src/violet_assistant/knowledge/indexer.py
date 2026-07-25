from __future__ import annotations

import hashlib
from pathlib import Path

from violet_assistant.ingestion.extractors import ExtractionError, extract_text
from violet_assistant.vector.chunker import chunk_text

_SUPPORTED = {
    ".txt", ".md", ".markdown", ".log", ".rst",
    ".csv", ".tsv", ".xlsx", ".xlsm", ".pdf", ".docx", ".json",
}


class KnowledgeIndexer:
    def __init__(
        self, embedder, store, knowledge_dir: Path, chunk_size=1000, chunk_overlap=150
    ):
        self.embedder = embedder
        self.store = store
        self.knowledge_dir = Path(knowledge_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def reindex(self, full: bool = False) -> dict:
        report = {"indexed": 0, "skipped": 0, "removed": 0, "chunks": 0, "errors": []}
        if not self.knowledge_dir.exists():
            return report
        seen_paths: set[str] = set()
        for path in sorted(self.knowledge_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _SUPPORTED:
                continue
            rel = str(path.relative_to(self.knowledge_dir).as_posix())
            seen_paths.add(rel)
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            existing = self.store.doc_by_path(rel)
            if not full and existing and existing["hash"] == digest:
                report["skipped"] += 1
                continue
            try:
                extracted = extract_text(path.name, data, max_chars=None)
                pieces = chunk_text(
                    extracted["text"], self.chunk_size, self.chunk_overlap
                )
                if not pieces:
                    raise ExtractionError("no chunks produced")
                vectors = await self.embedder.embed(pieces)
                doc_id = (
                    existing["doc_id"]
                    if existing
                    else hashlib.sha256(rel.encode()).hexdigest()[:16]
                )
                self.store.upsert_doc(
                    doc_id=doc_id,
                    path=rel,
                    version=digest,
                    mtime=path.stat().st_mtime,
                    chunks=list(zip(pieces, vectors)),
                    model=self.embedder.name,
                )
                report["indexed"] += 1
                report["chunks"] += len(pieces)
            except Exception as exc:  # noqa: BLE001 — one bad file must not stop the scan
                report["errors"].append({"path": rel, "error": str(exc)})
        # remove docs whose files are gone
        for doc in self.store.list_docs():
            if doc["path"] not in seen_paths:
                existing = self.store.doc_by_path(doc["path"])
                if existing:
                    self.store.delete_doc(existing["doc_id"])
                    report["removed"] += 1
        return report
