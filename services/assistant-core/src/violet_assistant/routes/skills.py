from __future__ import annotations

from fastapi import APIRouter

from violet_assistant.skills.registry import SkillRegistry


def create_skills_router(registry: SkillRegistry, enabled: bool) -> APIRouter:
    router = APIRouter()

    @router.get("/api/skills")
    async def skills() -> dict:
        return {
            "enabled": enabled,
            "items": [
                {
                    "id": skill.id,
                    "name": skill.name,
                    "description": skill.description,
                    "kind": skill.kind,
                }
                for skill in registry.list_skills()
            ],
        }

    return router
