from __future__ import annotations

from pydantic import BaseModel, Field


class AudioResult(BaseModel):
    text: str
    voice: str = "default"
    language: str = "id"
    audio_base64: str | None = None
    provider: str = "mock"


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    voice: str = "default"
    language: str = "id"


class ProviderHealth(BaseModel):
    provider: str
    status: str
    detail: str | None = None

