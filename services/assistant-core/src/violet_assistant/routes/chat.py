from __future__ import annotations

from fastapi import APIRouter

from violet_assistant.orchestrator.chat_orchestrator import ChatOrchestrator
from violet_assistant.schemas.chat import ChatRequest, ChatResponse


def create_chat_router(orchestrator: ChatOrchestrator) -> APIRouter:
    router = APIRouter()

    @router.post("/api/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        return await orchestrator.chat(request)

    return router

