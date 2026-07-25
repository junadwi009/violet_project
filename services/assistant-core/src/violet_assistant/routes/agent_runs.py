from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class ResumeRequest(BaseModel):
    tool_call_id: str
    approved: bool


def create_agent_runs_router(store, agent_loop, agent_registry) -> APIRouter:
    router = APIRouter()

    @router.get("/api/agent-runs/{run_id}")
    async def get_run(run_id: str) -> dict:
        row = store.get_agent_run(run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Unknown agent run.")
        return {
            "id": row["id"],
            "status": row["status"],
            "agent_id": row["agent_id"],
            "iterations": row["iterations"],
            "pending": json.loads(row["pending_json"]) if row["pending_json"] else [],
        }

    @router.post("/api/agent-runs/{run_id}/resume")
    async def resume(run_id: str, body: ResumeRequest) -> dict:
        row = store.get_agent_run(run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Unknown agent run.")
        if row["status"] != "awaiting_approval":
            raise HTTPException(
                status_code=409,
                detail=f"Run is {row['status']}, not awaiting approval.",
            )
        if agent_loop is None or agent_registry is None:
            raise HTTPException(status_code=409, detail="Agent tools are not enabled.")

        from violet_assistant.llm.base import Message

        agent = agent_registry.get(row["agent_id"])
        if agent is None:
            raise HTTPException(
                status_code=409, detail="The agent for this run is no longer available."
            )
        pending = json.loads(row["pending_json"] or "[]")
        target = next((p for p in pending if p["id"] == body.tool_call_id), None)
        if target is None:
            raise HTTPException(
                status_code=404, detail="Unknown tool_call_id for this run."
            )

        messages = [Message(**m) for m in json.loads(row["messages_json"])]
        outcome = await agent_loop.continue_run(
            agent, messages, row["iterations"], target, approved=body.approved
        )
        store.update_agent_run(
            run_id,
            status=outcome.status,
            messages=[m.__dict__ for m in outcome.messages],
            iterations=outcome.iterations,
            pending=outcome.pending or None,
        )
        return {
            "agent_run_id": run_id,
            "status": outcome.status,
            "text": outcome.text,
            "tool_trace": outcome.trace,
            "tool_requests": outcome.pending,
            "citations": outcome.citations,
            "artifacts": outcome.artifacts,
        }

    return router
