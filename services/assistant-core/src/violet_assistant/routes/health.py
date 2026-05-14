from __future__ import annotations

from fastapi import APIRouter

from violet_assistant.config import Settings
from violet_assistant.llm.base import LLMProvider
from violet_assistant.personality.loader import PersonalityLoader


def create_health_router(
    settings: Settings,
    provider: LLMProvider,
    personality_loader: PersonalityLoader,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict:
        provider_health = await provider.health()
        return {
            "status": "ok",
            "environment": settings.app_env,
            "provider": provider_health.__dict__,
            "personality_profiles": [
                profile.id for profile in personality_loader.list_profiles()
            ],
        }

    return router

