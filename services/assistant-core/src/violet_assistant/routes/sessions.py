from __future__ import annotations

from fastapi import APIRouter, HTTPException

from violet_assistant.persistence.sqlite_store import SQLiteStore


def create_sessions_router(store: SQLiteStore) -> APIRouter:
    router = APIRouter()

    @router.get("/api/sessions")
    async def sessions() -> dict:
        return {"items": store.list_sessions()}

    @router.get("/api/sessions/{session_id}/messages")
    async def session_messages(session_id: str) -> dict:
        return {"items": store.messages_for_session(session_id)}

    @router.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str) -> dict:
        try:
            return store.delete_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc

    @router.delete("/api/sessions")
    async def delete_all_sessions() -> dict:
        return store.delete_all_sessions()

    return router
