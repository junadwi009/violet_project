from __future__ import annotations

from fastapi import APIRouter

from violet_assistant.agents.registry import AgentRegistry


def create_agents_router(registry: AgentRegistry, enabled: bool) -> APIRouter:
    router = APIRouter()

    @router.get("/api/agents")
    async def agents() -> dict:
        return {
            "enabled": enabled,
            "items": [
                {
                    "id": agent.id,
                    "name": agent.name,
                    "description": agent.description,
                    "model": agent.model,
                }
                for agent in registry.list_agents()
            ],
        }

    return router
