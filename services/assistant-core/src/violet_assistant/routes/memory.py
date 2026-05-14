from __future__ import annotations

from fastapi import APIRouter, HTTPException

from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.schemas.memory import (
    MemoryActionResponse,
    MemoryCandidateUpdate,
    MemoryUpdate,
)


def create_memory_router(store: SQLiteStore) -> APIRouter:
    router = APIRouter()

    @router.get("/api/memory/candidates")
    async def memory_candidates() -> dict:
        return {"items": store.pending_memory_candidates()}

    @router.patch("/api/memory/candidates/{candidate_id}")
    async def update_memory_candidate(
        candidate_id: str, update: MemoryCandidateUpdate
    ) -> dict:
        try:
            return store.update_memory_candidate(
                candidate_id,
                content=update.content,
                memory_type=update.memory_type,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Memory candidate not found") from exc

    @router.post(
        "/api/memory/candidates/{candidate_id}/approve",
        response_model=MemoryActionResponse,
    )
    async def approve_memory_candidate(candidate_id: str) -> dict:
        try:
            return store.approve_memory_candidate(candidate_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Memory candidate not found") from exc

    @router.post(
        "/api/memory/candidates/{candidate_id}/reject",
        response_model=MemoryActionResponse,
    )
    async def reject_memory_candidate(candidate_id: str) -> dict:
        try:
            return store.reject_memory_candidate(candidate_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Memory candidate not found") from exc

    @router.get("/api/memory")
    async def memories() -> dict:
        return {"items": store.approved_memories()}

    @router.patch("/api/memory/{memory_id}")
    async def update_memory(memory_id: str, update: MemoryUpdate) -> dict:
        try:
            return store.update_memory(
                memory_id,
                content=update.content,
                memory_type=update.memory_type,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Memory not found") from exc

    @router.delete("/api/memory/{memory_id}", response_model=MemoryActionResponse)
    async def delete_memory(memory_id: str) -> dict:
        try:
            return store.delete_memory(memory_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Memory not found") from exc

    return router
