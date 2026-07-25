from __future__ import annotations

from violet_assistant.ingestion.extractors import ExtractionError, extract_text
from violet_assistant.vector.chunker import chunk_text


class KnowledgeIndexer:
    def __init__(self, embedder, store, sources, chunk_size=1000, chunk_overlap=150):
        self.embedder = embedder
        self.store = store
        self.sources = list(sources)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def reindex(self, full: bool = False, only: str | None = None) -> dict:
        report = {
            "indexed": 0, "skipped": 0, "removed": 0, "chunks": 0,
            "errors": [], "sources": {},
        }
        for source in self.sources:
            if only is not None and source.name != only:
                continue
            per = {"indexed": 0, "skipped": 0, "removed": 0, "chunks": 0, "errors": []}
            seen: set[str] = set()
            try:
                documents = list(source.list_documents())
            except Exception as exc:  # noqa: BLE001 — a dead source must not kill others
                per["errors"].append({"path": source.name, "error": str(exc)})
                report["sources"][source.name] = per
                report["errors"].extend(per["errors"])
                continue
            for doc in documents:
                seen.add(doc.doc_id)
                existing = self.store.doc_by_id(doc.doc_id)
                if not full and existing and existing["version"] == doc.version:
                    per["skipped"] += 1
                    continue
                try:
                    data = source.read(doc)
                    extracted = extract_text(doc.filename, data, max_chars=None)
                    pieces = chunk_text(
                        extracted["text"], self.chunk_size, self.chunk_overlap
                    )
                    if not pieces:
                        raise ExtractionError("no chunks produced")
                    vectors = await self.embedder.embed(pieces)
                    self.store.upsert_doc(
                        doc_id=doc.doc_id,
                        path=doc.display_path,
                        version=doc.version,
                        mtime=0.0,
                        chunks=list(zip(pieces, vectors)),
                        model=self.embedder.name,
                        origin=source.name,
                    )
                    per["indexed"] += 1
                    per["chunks"] += len(pieces)
                except Exception as exc:  # noqa: BLE001
                    per["errors"].append({"path": doc.display_path, "error": str(exc)})
            per["removed"] = self.store.delete_missing(source.name, seen)
            report["sources"][source.name] = per
            for key in ("indexed", "skipped", "removed", "chunks"):
                report[key] += per[key]
            report["errors"].extend(per["errors"])
        return report
