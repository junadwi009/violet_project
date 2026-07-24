from __future__ import annotations

from fastapi import APIRouter

from violet_assistant.persistence.sqlite_store import SQLiteStore


def create_sessions_router(store: SQLiteStore) -> APIRouter:
    router = APIRouter()

    @router.get("/api/sessions")
    async def sessions() -> dict:
        return {"items": store.list_sessions()}

    @router.get("/api/sessions/{session_id}/messages")
    async def session_messages(session_id: str) -> dict:
        return {"items": store.messages_for_session(session_id)}

    return router
