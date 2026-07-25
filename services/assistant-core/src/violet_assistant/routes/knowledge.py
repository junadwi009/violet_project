from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class ReindexRequest(BaseModel):
    full: bool = False


def create_knowledge_router(indexer, store, knowledge_dir: str, model: str) -> APIRouter:
    router = APIRouter()

    @router.get("/api/knowledge")
    async def status() -> dict:
        stats = store.stats() if store else {"doc_count": 0, "chunk_count": 0}
        docs = store.list_docs() if store else []
        return {
            "dir": str(knowledge_dir),
            "provider": model,
            "enabled": indexer is not None,
            "doc_count": stats["doc_count"],
            "chunk_count": stats["chunk_count"],
            "docs": docs,
        }

    @router.post("/api/knowledge/reindex")
    async def reindex(body: ReindexRequest) -> dict:
        if indexer is None:
            raise HTTPException(
                status_code=409,
                detail="Knowledge base is not enabled (set RAG_PROVIDER=vector).",
            )
        return await indexer.reindex(full=body.full)

    return router
