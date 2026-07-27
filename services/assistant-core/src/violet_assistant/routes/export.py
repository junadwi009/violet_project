from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Response

from violet_assistant.config import Settings
from violet_assistant.memory.store.base import ApprovedMemoryStore
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.preferences.store import PreferencesStore


def create_export_router(
    store: SQLiteStore,
    memory_store: ApprovedMemoryStore,
    preferences: PreferencesStore,
    settings: Settings,
) -> APIRouter:
    """A user-data backup: sessions, messages, memories, preference overrides.

    Deliberately excludes the ``locked`` safety block — this is a backup, not a
    config dump, and it should not carry a snapshot of the deployment's safety
    posture into a file that gets emailed around.
    """
    router = APIRouter()

    @router.get("/api/export")
    async def export_bundle() -> Response:
        sessions = store.list_sessions()
        bundle = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": 1,
            "sessions": sessions,
            "messages": [
                {**message, "session_id": session["id"]}
                for session in sessions
                for message in store.messages_for_session(session["id"])
            ],
            "memories": memory_store.list(),
            "preferences": {
                "values": preferences.effective(settings),
                "overridden": preferences.overridden(),
            },
        }
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return Response(
            content=json.dumps(bundle, indent=2, default=str),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="violet-export-{stamp}.json"'
            },
        )

    return router
