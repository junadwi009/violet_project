from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass(frozen=True)
class SourceDocument:
    doc_id: str        # namespaced + stable, e.g. "local:notes.md" / "gdrive:<id>"
    display_path: str   # unique human label
    version: str        # change token: content hash | md5Checksum | modifiedTime
    filename: str       # name with extension (drives extractor selection)
    mime: str = ""      # source mime (Drive export decisions)


class KnowledgeSource(Protocol):
    name: str  # also the `origin` stored per doc

    def status(self) -> dict: ...
    def list_documents(self) -> Iterable[SourceDocument]: ...
    def read(self, doc: SourceDocument) -> bytes: ...
