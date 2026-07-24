from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Chunk:
    """A retrieved context fragment.

    This is the frozen contract shared between Track 2 (RAG) and Track 3 (Vector).
    Freeze changes here through a coordinated log entry — both tracks depend on it.
    """

    text: str
    source: str = "unknown"
    score: float = 0.0
    metadata: dict[str, str] = field(default_factory=dict)


class Retriever(Protocol):
    name: str

    async def retrieve(self, query: str, k: int = 4) -> list[Chunk]:
        """Return up to ``k`` context chunks relevant to ``query`` (empty list if none)."""
