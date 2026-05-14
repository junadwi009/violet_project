from __future__ import annotations

from dataclasses import dataclass

from violet_assistant.schemas.chat import MemoryCandidateResponse


@dataclass(frozen=True)
class MemoryCandidate:
    id: str
    memory_type: str
    content: str
    reason: str
    source_message_id: str
    confidence: float
    status: str = "pending"

    def to_response(self) -> MemoryCandidateResponse:
        return MemoryCandidateResponse(
            id=self.id,
            memory_type=self.memory_type,
            content=self.content,
            reason=self.reason,
            source_message_id=self.source_message_id,
            confidence=self.confidence,
            status=self.status,
        )

