from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from violet_assistant.persistence.sqlite_store import SQLiteStore

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = PROJECT_ROOT / "database" / "migrations" / "001_init.sql"


def _store(tmp_path):
    store = SQLiteStore(db_path=tmp_path / "v.db", migration_path=MIGRATION_PATH)
    store.initialize()
    return store


def test_migration_runner_applies_every_sql_file(tmp_path):
    store = _store(tmp_path)
    with sqlite3.connect(store.db_path) as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "sessions" in names       # from 001
    assert "agent_runs" in names     # from 002


def test_agent_run_round_trip(tmp_path):
    store = _store(tmp_path)
    run_id = store.create_agent_run(
        session_id="s1",
        agent_id="a1",
        messages=[{"role": "user", "content": "hi"}],
        iterations=1,
        status="awaiting_approval",
        pending=[{"id": "c1", "tool": "echo"}],
    )
    row = store.get_agent_run(run_id)
    assert row["status"] == "awaiting_approval"
    assert json.loads(row["messages_json"])[0]["content"] == "hi"
    assert json.loads(row["pending_json"])[0]["tool"] == "echo"

    store.update_agent_run(
        run_id, status="completed", messages=[], iterations=2, pending=None
    )
    row = store.get_agent_run(run_id)
    assert row["status"] == "completed"
    assert row["iterations"] == 2
    assert row["pending_json"] is None
    assert store.get_agent_run("nope") is None


def test_tool_audit_log_written(tmp_path):
    store = _store(tmp_path)
    store.add_tool_audit_log("fetch_url", "url=https://x", "medium", False, "declined")
    store.add_tool_audit_log("knowledge_search", "query=violet", "low", True, "3 hits")
    rows = store.list_tool_audit_logs(limit=10)
    assert len(rows) == 2
    assert {r["tool_name"] for r in rows} == {"fetch_url", "knowledge_search"}
    declined = [r for r in rows if r["tool_name"] == "fetch_url"][0]
    assert declined["approved"] == 0
