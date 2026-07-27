from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException

from violet_assistant.memory.schema import MemoryCandidate
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.routes.sessions import create_sessions_router

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = PROJECT_ROOT / "database" / "migrations" / "001_init.sql"


@pytest.fixture()
def store(tmp_path):
    s = SQLiteStore(db_path=tmp_path / "test.db", migration_path=MIGRATION_PATH)
    s.initialize()
    return s


def _seed(store: SQLiteStore, session_id: str) -> str:
    """Create a session with one message; return the message id."""
    store.ensure_session(session_id, title=f"title-{session_id}")
    return store.add_message(session_id, role="user", content="hello")


def _seed_candidate(
    store: SQLiteStore, candidate_id: str, message_id: str, status: str = "pending"
) -> None:
    store.add_memory_candidates(
        [
            MemoryCandidate(
                id=candidate_id,
                memory_type="fact",
                content=f"content-{candidate_id}",
                reason="stated",
                source_message_id=message_id,
                confidence=0.8,
                status=status,
            )
        ]
    )


def _seed_audit_log(store: SQLiteStore, tool_name: str) -> None:
    store.add_tool_audit_log(tool_name, "query=violet", "low", True, "ok")


def _endpoint(router, method: str, path: str):
    for route in router.routes:
        if route.path == path and method in route.methods:
            return route.endpoint
    raise KeyError(f"{method} {path}")


def _all_candidate_ids(store: SQLiteStore) -> set[str]:
    """Read every memory_candidates row regardless of status, via a plain connection."""
    with sqlite3.connect(store.db_path) as connection:
        rows = connection.execute("SELECT id FROM memory_candidates").fetchall()
    return {row[0] for row in rows}


class _RaisesOnSessionsDelete(sqlite3.Connection):
    """Connection subclass that fails the final `DELETE FROM sessions` statement.

    Everything else (the candidates/agent_runs/messages deletes that run earlier
    in the same transaction, and any read) passes straight through to the real
    sqlite3.Connection.execute.
    """

    def execute(self, sql, *args, **kwargs):
        if sql.strip().startswith("DELETE FROM sessions"):
            raise RuntimeError("simulated failure deleting the sessions row")
        return super().execute(sql, *args, **kwargs)


def _guarded_connect(self: SQLiteStore) -> sqlite3.Connection:
    connection = sqlite3.connect(self.db_path, factory=_RaisesOnSessionsDelete)
    connection.row_factory = sqlite3.Row
    return connection


# --- deletions -------------------------------------------------------------


def test_delete_session_removes_messages(store):
    _seed(store, "s1")
    _seed(store, "s2")

    report = store.delete_session("s1")

    assert report["deleted_sessions"] == 1
    assert report["deleted_messages"] == 1
    assert [s["id"] for s in store.list_sessions()] == ["s2"]
    assert store.messages_for_session("s1") == []
    assert len(store.messages_for_session("s2")) == 1


def test_delete_session_removes_orphaned_candidates(store):
    message_id = _seed(store, "s1")
    other_message_id = _seed(store, "s2")
    _seed_candidate(store, "c1", message_id)
    _seed_candidate(store, "c2", other_message_id)
    assert len(store.pending_memory_candidates()) == 2

    report = store.delete_session("s1")

    assert report["deleted_candidates"] == 1
    assert [c["id"] for c in store.pending_memory_candidates()] == ["c2"]


def test_delete_session_removes_non_pending_candidates(store):
    message_id = _seed(store, "s1")
    other_message_id = _seed(store, "s2")
    _seed_candidate(store, "c1", message_id, status="pending")
    _seed_candidate(store, "c2", message_id, status="approved")
    _seed_candidate(store, "c3", message_id, status="rejected")
    _seed_candidate(store, "c4", other_message_id, status="pending")
    assert _all_candidate_ids(store) == {"c1", "c2", "c3", "c4"}

    report = store.delete_session("s1")

    assert report["deleted_candidates"] == 3
    assert _all_candidate_ids(store) == {"c4"}


def test_delete_session_removes_agent_runs(store):
    _seed(store, "s1")
    _seed(store, "s2")
    doomed = store.create_agent_run(
        session_id="s1",
        agent_id="a1",
        messages=[{"role": "user", "content": "hi"}],
        iterations=1,
        status="awaiting_approval",
        pending=None,
    )
    survivor = store.create_agent_run(
        session_id="s2",
        agent_id="a1",
        messages=[{"role": "user", "content": "hi"}],
        iterations=1,
        status="awaiting_approval",
        pending=None,
    )

    report = store.delete_session("s1")

    assert report["deleted_agent_runs"] == 1
    assert store.get_agent_run(doomed) is None
    assert store.get_agent_run(survivor) is not None


def test_delete_unknown_session_raises(store):
    with pytest.raises(KeyError):
        store.delete_session("missing")


def test_delete_session_rolls_back_all_children_on_final_delete_failure(store, monkeypatch):
    """The four deletes run in one transaction: if the last one (sessions) fails,
    the candidates/agent_runs/messages deletes that already ran must roll back too.

    This is a regression guard against a plausible future "consistency" refactor
    that swaps the single-transaction `with self._connect()` for autocommit +
    rowcount-based absence detection (matching the pattern `delete_memory` already
    uses a few lines above) — a change that would pass every other test in this
    file while quietly destroying the atomicity guarantee.
    """
    message_id = _seed(store, "s1")
    _seed_candidate(store, "c1", message_id)
    run_id = store.create_agent_run(
        session_id="s1",
        agent_id="a1",
        messages=[{"role": "user", "content": "hi"}],
        iterations=1,
        status="awaiting_approval",
        pending=None,
    )

    monkeypatch.setattr(SQLiteStore, "_connect", _guarded_connect)
    with pytest.raises(RuntimeError):
        store.delete_session("s1")
    monkeypatch.undo()  # read back through the normal, unguarded connection path

    assert [s["id"] for s in store.list_sessions()] == ["s1"]
    assert len(store.messages_for_session("s1")) == 1
    assert [c["id"] for c in store.pending_memory_candidates()] == ["c1"]
    assert store.get_agent_run(run_id) is not None


def test_delete_all_sessions(store):
    _seed(store, "s1")
    _seed(store, "s2")
    store.create_agent_run(
        session_id="s1",
        agent_id="a1",
        messages=[],
        iterations=0,
        status="completed",
        pending=None,
    )

    report = store.delete_all_sessions()

    assert report["deleted_sessions"] == 2
    assert report["deleted_messages"] == 2
    assert report["deleted_agent_runs"] == 1
    assert store.list_sessions() == []
    assert store.messages_for_session("s1") == []
    assert store.messages_for_session("s2") == []


def test_delete_all_sessions_removes_candidates(store):
    message_id = _seed(store, "s1")
    other_message_id = _seed(store, "s2")
    _seed_candidate(store, "c1", message_id)
    _seed_candidate(store, "c2", other_message_id)

    report = store.delete_all_sessions()

    assert report["deleted_candidates"] == 2
    assert store.pending_memory_candidates() == []


def test_delete_all_sessions_removes_non_pending_candidates(store):
    message_id = _seed(store, "s1")
    _seed_candidate(store, "c1", message_id, status="pending")
    _seed_candidate(store, "c2", message_id, status="approved")
    _seed_candidate(store, "c3", message_id, status="rejected")
    assert _all_candidate_ids(store) == {"c1", "c2", "c3"}

    report = store.delete_all_sessions()

    assert report["deleted_candidates"] == 3
    assert _all_candidate_ids(store) == set()


def test_delete_all_sessions_rolls_back_all_children_on_final_delete_failure(
    store, monkeypatch
):
    """Same atomicity guard as delete_session's, but for the unscoped variant:
    if the final `DELETE FROM sessions` fails, the candidates/agent_runs/messages
    deletes that already ran in the same transaction must roll back too.
    """
    message_id = _seed(store, "s1")
    _seed_candidate(store, "c1", message_id)
    run_id = store.create_agent_run(
        session_id="s1",
        agent_id="a1",
        messages=[{"role": "user", "content": "hi"}],
        iterations=1,
        status="awaiting_approval",
        pending=None,
    )

    monkeypatch.setattr(SQLiteStore, "_connect", _guarded_connect)
    with pytest.raises(RuntimeError):
        store.delete_all_sessions()
    monkeypatch.undo()  # read back through the normal, unguarded connection path

    assert [s["id"] for s in store.list_sessions()] == ["s1"]
    assert len(store.messages_for_session("s1")) == 1
    assert [c["id"] for c in store.pending_memory_candidates()] == ["c1"]
    assert store.get_agent_run(run_id) is not None


# --- preservations ---------------------------------------------------------


def test_delete_session_preserves_audit_logs(store):
    _seed(store, "s1")
    _seed_audit_log(store, "knowledge_search")
    _seed_audit_log(store, "fetch_url")
    before = store.list_tool_audit_logs()
    assert len(before) == 2

    store.delete_session("s1")

    after = store.list_tool_audit_logs()
    assert len(after) == 2
    assert {row["tool_name"] for row in after} == {"knowledge_search", "fetch_url"}


def test_delete_session_preserves_approved_memories(store):
    message_id = _seed(store, "s1")
    store.insert_memory(
        memory_type="fact",
        content="user likes tea",
        source=f"message:{message_id}",
        confidence=0.9,
    )
    assert len(store.approved_memories()) == 1

    store.delete_session("s1")

    remaining = store.approved_memories()
    assert len(remaining) == 1
    assert remaining[0]["content"] == "user likes tea"


def test_delete_all_sessions_preserves_audit_logs_and_memories(store):
    _seed(store, "s1")
    _seed(store, "s2")
    _seed_audit_log(store, "knowledge_search")
    store.insert_memory(
        memory_type="fact",
        content="user likes tea",
        source="message:x",
        confidence=0.9,
    )

    store.delete_all_sessions()

    assert len(store.list_tool_audit_logs()) == 1
    assert [m["content"] for m in store.approved_memories()] == ["user likes tea"]


# --- routes ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_route_404_on_unknown(store):
    router = create_sessions_router(store)
    with pytest.raises(HTTPException) as exc_info:
        await _endpoint(router, "DELETE", "/api/sessions/{session_id}")("missing")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_routes_roundtrip(store):
    _seed(store, "s1")
    router = create_sessions_router(store)

    body = await _endpoint(router, "DELETE", "/api/sessions/{session_id}")("s1")
    assert body["deleted_sessions"] == 1
    assert body["deleted_messages"] == 1

    _seed(store, "s2")
    body = await _endpoint(router, "DELETE", "/api/sessions")()
    assert body["deleted_sessions"] == 1
    assert store.list_sessions() == []


@pytest.mark.asyncio
async def test_existing_session_routes_still_work(store):
    _seed(store, "s1")
    router = create_sessions_router(store)

    listed = await _endpoint(router, "GET", "/api/sessions")()
    assert [s["id"] for s in listed["items"]] == ["s1"]

    messages = await _endpoint(
        router, "GET", "/api/sessions/{session_id}/messages"
    )("s1")
    assert len(messages["items"]) == 1
