from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class ReindexRequest(BaseModel):
    full: bool = False
    source: str | None = None


def create_knowledge_router(
    indexer, store, knowledge_dir, model, sources=None, gdrive_source=None, settings=None
):
    # Defaults keep the Phase A 4-arg call sites (and their tests) working unchanged.
    router = APIRouter()

    @router.get("/api/knowledge")
    async def status() -> dict:
        stats = store.stats() if store else {"doc_count": 0, "chunk_count": 0}
        return {
            "dir": str(knowledge_dir),
            "provider": model,
            "enabled": indexer is not None,
            "doc_count": stats["doc_count"],
            "chunk_count": stats["chunk_count"],
            "docs": store.list_docs() if store else [],
            "sources": [s.status() for s in (sources or [])],
        }

    @router.post("/api/knowledge/reindex")
    async def reindex(body: ReindexRequest) -> dict:
        if indexer is None:
            raise HTTPException(
                status_code=409,
                detail="Knowledge base is not enabled (set RAG_PROVIDER=vector).",
            )
        return await indexer.reindex(full=body.full, only=body.source)

    @router.get("/api/knowledge/gdrive/status")
    async def gdrive_status() -> dict:
        if gdrive_source is None:
            return {"name": "gdrive", "connected": False, "detail": "not_configured"}
        return gdrive_source.status()

    @router.post("/api/knowledge/gdrive/connect")
    async def gdrive_connect() -> dict:
        if gdrive_source is None or settings is None:
            raise HTTPException(status_code=400, detail="Google Drive is not configured.")
        from violet_assistant.knowledge import gdrive_auth

        try:
            gdrive_auth.authorize(settings)  # opens the local browser (one-time)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return gdrive_source.status()

    @router.post("/api/knowledge/gdrive/disconnect")
    async def gdrive_disconnect() -> dict:
        if settings is not None:
            from violet_assistant.knowledge import gdrive_auth

            gdrive_auth.revoke(settings)
        return {"name": "gdrive", "connected": False, "detail": "not_configured"}

    return router
