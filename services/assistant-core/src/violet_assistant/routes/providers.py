from __future__ import annotations

from fastapi import APIRouter

from violet_assistant.config import Settings
from violet_assistant.llm.registry import describe_providers


def create_providers_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/api/providers")
    async def providers() -> dict:
        return describe_providers(settings)

    return router
