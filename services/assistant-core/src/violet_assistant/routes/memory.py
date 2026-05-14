from __future__ import annotations

from fastapi import APIRouter

from violet_assistant.persistence.sqlite_store import SQLiteStore


def create_memory_router(store: SQLiteStore) -> APIRouter:
    router = APIRouter()

    @router.get("/api/memory/candidates")
    async def memory_candidates() -> dict:
        return {"items": store.pending_memory_candidates()}

    return router

