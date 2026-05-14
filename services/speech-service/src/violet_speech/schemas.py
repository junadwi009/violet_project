from __future__ import annotations

from pydantic import BaseModel, Field


class Transcript(BaseModel):
    text: str
    language: str = "id"
    confidence: float = 1.0
    provider: str = "mock"


class TranscribeRequest(BaseModel):
    text: str = Field(default="", max_length=12000)
    language: str = "id"


class ProviderHealth(BaseModel):
    provider: str
    status: str
    detail: str | None = None

