from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.routes.agent_runs import ResumeRequest, create_agent_runs_router

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = PROJECT_ROOT / "database" / "migrations" / "001_init.sql"


def _endpoint(router, method, suffix):
    for route in router.routes:
        if method in route.methods and route.path.endswith(suffix):
            return route.endpoint
    raise KeyError(f"{method} {suffix}")


def _store(tmp_path):
    store = SQLiteStore(db_path=tmp_path / "v.db", migration_path=MIGRATION_PATH)
    store.initialize()
    return store


@pytest.mark.asyncio
async def test_resume_unknown_run_is_404(tmp_path):
    router = create_agent_runs_router(_store(tmp_path), None, None)
    with pytest.raises(HTTPException) as exc:
        await _endpoint(router, "POST", "/resume")(
            "nope", ResumeRequest(tool_call_id="c", approved=True)
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_resume_non_paused_run_is_409(tmp_path):
    store = _store(tmp_path)
    run_id = store.create_agent_run("s", "a", [], 1, "completed", None)
    router = create_agent_runs_router(store, None, None)
    with pytest.raises(HTTPException) as exc:
        await _endpoint(router, "POST", "/resume")(
            run_id, ResumeRequest(tool_call_id="c", approved=True)
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_get_run_status(tmp_path):
    store = _store(tmp_path)
    run_id = store.create_agent_run(
        "s", "a", [], 2, "awaiting_approval", [{"id": "c1", "tool": "echo"}]
    )
    router = create_agent_runs_router(store, None, None)
    body = await _endpoint(router, "GET", "{run_id}")(run_id)
    assert body["status"] == "awaiting_approval"
    assert body["iterations"] == 2
    assert body["pending"][0]["tool"] == "echo"
