from __future__ import annotations

from fastapi import APIRouter, HTTPException

from violet_assistant.memory.store.base import ApprovedMemoryStore
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.schemas.memory import (
    MemoryActionResponse,
    MemoryCandidateUpdate,
    MemoryUpdate,
)


def create_memory_router(
    store: SQLiteStore, memory_store: ApprovedMemoryStore
) -> APIRouter:
    """Candidates live in ``store`` (SQLite); approved memories live in ``memory_store``
    (files by default, or sqlite)."""
    router = APIRouter()

    @router.get("/api/memory/info")
    async def memory_info() -> dict:
        return {
            "backend": memory_store.backend_name,
            "location": memory_store.location(),
        }

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
        candidate = store.get_pending_candidate(candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Memory candidate not found")
        record = memory_store.add(
            memory_type=candidate["memory_type"],
            content=candidate["content"],
            source=f"message:{candidate['source_message_id']}",
            confidence=candidate["confidence"],
            candidate_id=candidate_id,
        )
        store.mark_candidate_approved(candidate_id)
        return {"id": candidate_id, "status": "approved", "memory_id": record["id"]}

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
        return {"items": memory_store.list()}

    @router.patch("/api/memory/{memory_id}")
    async def update_memory(memory_id: str, update: MemoryUpdate) -> dict:
        try:
            return memory_store.update(
                memory_id,
                content=update.content,
                memory_type=update.memory_type,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Memory not found") from exc

    @router.delete("/api/memory/{memory_id}", response_model=MemoryActionResponse)
    async def delete_memory(memory_id: str) -> dict:
        try:
            result = memory_store.delete(memory_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Memory not found") from exc
        return {
            "id": memory_id,
            "status": result.get("status", "deleted"),
            "memory_id": memory_id,
        }

    return router
