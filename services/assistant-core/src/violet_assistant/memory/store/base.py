from __future__ import annotations

from typing import Any, Protocol


# Approved-memory records are plain dicts shaped like the /api/memory response so the
# API and frontend do not care which backend produced them:
#   {id, memory_type, content, source, confidence, approved, created_at, updated_at}
MemoryRecord = dict[str, Any]


class ApprovedMemoryStore(Protocol):
    backend_name: str

    def location(self) -> str:
        """Human-readable location of the store (dir path or db path) for the UI readout."""

    def list(self) -> list[MemoryRecord]:
        """Return approved memories, newest first."""

    def add(
        self,
        *,
        memory_type: str,
        content: str,
        source: str,
        confidence: float,
        candidate_id: str | None = None,
    ) -> MemoryRecord:
        """Persist a newly approved memory and return the stored record."""

    def update(
        self, memory_id: str, content: str, memory_type: str | None = None
    ) -> MemoryRecord:
        """Update an approved memory. Raise KeyError if it does not exist."""

    def delete(self, memory_id: str) -> MemoryRecord:
        """Delete an approved memory. Raise KeyError if it does not exist."""
