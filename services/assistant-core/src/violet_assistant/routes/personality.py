from __future__ import annotations

from fastapi import APIRouter

from violet_assistant.personality.loader import PersonalityLoader


def create_personality_router(personality_loader: PersonalityLoader) -> APIRouter:
    router = APIRouter()

    @router.get("/api/personalities")
    async def personalities() -> dict:
        return {
            "items": [
                {
                    "id": profile.id,
                    "name": profile.name,
                    "tone": profile.tone,
                    "verbosity": profile.verbosity,
                    "language": profile.language,
                }
                for profile in personality_loader.list_profiles()
            ]
        }

    return router

