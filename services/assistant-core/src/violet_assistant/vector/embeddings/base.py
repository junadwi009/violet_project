from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    name: str

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text. All vectors share the same dimension."""
