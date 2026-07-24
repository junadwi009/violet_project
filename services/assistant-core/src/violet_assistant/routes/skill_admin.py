from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from violet_assistant.agents.registry import AgentRegistry
from violet_assistant.agents.vetting import (
    batch_report,
    build_library,
    candidate_from_text,
    judge_candidate,
    merge_skills,
    nearest_matches,
    resolve_ref,
    rule_verdict,
)
from violet_assistant.llm.base import LLMProvider
from violet_assistant.skills.registry import SkillRegistry


class CheckRequest(BaseModel):
    content: str = Field(min_length=1, max_length=60000)
    judge: bool = False


class MergeRequest(BaseModel):
    refs: list[str] = Field(min_length=2, max_length=8)
    name: str = Field(min_length=1, max_length=80)


class BatchItem(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=60000)


class BatchRequest(BaseModel):
    items: list[BatchItem] = Field(min_length=1, max_length=50)
    judge: bool = False


def create_skill_admin_router(
    skill_registry: SkillRegistry,
    agent_registry: AgentRegistry,
    provider: LLMProvider | None,
    default_model: str,
) -> APIRouter:
    router = APIRouter()

    def _library():
        return build_library(skill_registry, agent_registry)

    @router.get("/api/skills/library")
    async def library() -> dict:
        return {
            "judge_enabled": provider is not None,
            "items": [
                {"id": e.id, "kind": e.kind, "name": e.name, "description": e.description}
                for e in _library()
            ],
        }

    @router.post("/api/skills/check")
    async def check(request: CheckRequest) -> dict:
        try:
            candidate = candidate_from_text(request.content, "candidate", default_model)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        lib = _library()
        matches = nearest_matches(candidate, lib)
        result = {
            "candidate": {
                "name": candidate.name,
                "triggers": candidate.triggers,
                "chars": len(candidate.system_prompt),
            },
            "rule": rule_verdict(candidate, matches),
            "nearest": [
                {
                    "id": m.entry.id,
                    "kind": m.entry.kind,
                    "name": m.entry.name,
                    "similarity": m.similarity,
                    "shared_triggers": m.shared_triggers,
                }
                for m in matches
            ],
            "llm": None,
        }
        if request.judge and provider is not None:
            result["llm"] = await judge_candidate(candidate, lib, provider, default_model)
        return result

    @router.post("/api/skills/merge")
    async def merge(request: MergeRequest) -> dict:
        if provider is None:
            raise HTTPException(status_code=503, detail="Merge needs an LLM key (OPENROUTER_API_KEY).")
        resolved = [
            resolve_ref(ref, skill_registry, agent_registry, default_model) for ref in request.refs
        ]
        missing = [ref for ref, got in zip(request.refs, resolved) if got is None]
        if missing:
            raise HTTPException(status_code=404, detail=f"Unknown skill/agent id(s): {missing}")
        skill_md = await merge_skills(
            [a for a in resolved if a is not None], request.name, provider, default_model
        )
        return {"skill_md": skill_md}

    @router.post("/api/skills/batch")
    async def batch(request: BatchRequest) -> dict:
        lib = _library()
        installed = {e.id for e in lib if e.kind == "agent"}
        candidates = []
        invalid = []
        for item in request.items:
            try:
                candidates.append(candidate_from_text(item.content, item.id, default_model))
            except ValueError as exc:
                invalid.append({"id": item.id, "reason": str(exc)})
        rows = batch_report(candidates, lib, installed)
        by_id = {c.id: c for c in candidates}
        if request.judge and provider is not None:
            for row in rows:
                if not row["installed"]:
                    row["llm"] = (
                        await judge_candidate(by_id[row["id"]], lib, provider, default_model)
                    ).get("verdict")
        return {"rows": rows, "invalid": invalid, "judge_enabled": provider is not None}

    return router
