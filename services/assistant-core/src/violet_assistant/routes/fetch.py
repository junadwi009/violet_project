from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from violet_assistant.web.fetch import fetch_url


class FetchRequest(BaseModel):
    url: str


def create_fetch_router() -> APIRouter:
    router = APIRouter()

    @router.post("/api/fetch")
    async def fetch(body: FetchRequest) -> dict:
        try:
            result = await asyncio.to_thread(fetch_url, body.url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "url": result.url,
            "title": result.title,
            "text": result.text,
            "chars": result.chars,
            "truncated": result.truncated,
        }

    return router
