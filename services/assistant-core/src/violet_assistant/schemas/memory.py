from __future__ import annotations

from pydantic import BaseModel, Field


class MemoryCandidateUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    memory_type: str | None = Field(default=None, max_length=80)


class MemoryUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    memory_type: str | None = Field(default=None, max_length=80)


class MemoryActionResponse(BaseModel):
    id: str
    status: str
    memory_id: str | None = None

