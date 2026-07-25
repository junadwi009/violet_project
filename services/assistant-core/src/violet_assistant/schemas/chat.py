from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatContext(BaseModel):
    gesture: str | None = None
    client_state: str = "active"


class ChatRequest(BaseModel):
    session_id: str | None = None
    input_type: Literal["text"] = "text"
    content: str = Field(min_length=1, max_length=12000)
    personality_id: str = "violet.default"
    provider: str | None = None
    agent: str | None = None
    skill_id: str | None = None
    web_search: bool = False
    context: ChatContext = Field(default_factory=ChatContext)


class MemoryCandidateResponse(BaseModel):
    id: str
    memory_type: str
    content: str
    reason: str
    source_message_id: str
    confidence: float
    status: str = "pending"


class Artifact(BaseModel):
    id: str
    kind: str  # "chartjs" | "html" | "docx" | "pptx"
    title: str = ""
    spec: dict[str, Any] | None = None
    html: str | None = None
    # Downloadable file artifacts (docx/pptx): base64 content + filename + mime.
    file_base64: str | None = None
    filename: str | None = None
    mime: str | None = None


class ChatResponse(BaseModel):
    message_id: str
    session_id: str
    text: str
    emotion: str = "neutral"
    memory_candidates: list[MemoryCandidateResponse] = Field(default_factory=list)
    tool_requests: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    agent: str | None = None
    citations: list[str] = Field(default_factory=list)

