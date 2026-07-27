from __future__ import annotations

import hmac
import json
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from violet_assistant.config import Settings
from violet_assistant.memory.store.base import ApprovedMemoryStore
from violet_assistant.persistence.sqlite_store import SQLiteStore
from violet_assistant.preferences.store import PreferencesStore


def _require_api_token(settings: Settings) -> Callable:
    """Bearer-token gate for the export bundle.

    Fails closed: with ``VIOLET_API_TOKEN`` unset the endpoint is *disabled*
    (503), not open. `main.py`'s CORS policy allows every localhost origin with
    credentials, so any local page — another dev server, an Electron app, a
    postinstall script that opens a listener — can `fetch('/api/export')` and
    read the response. This is one GET that returns every session, message and
    memory, so it must not answer to a drive-by request.

    Known limit: the web client is legitimately cross-origin (Vite 5173 → API
    8000) and will have to carry the token, so anything that can read the
    client's bundle can read the token. This raises the bar; it is not airtight.
    """

    async def dependency(authorization: str | None = Header(default=None)) -> None:
        expected = settings.violet_api_token
        if not expected:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Export is disabled until VIOLET_API_TOKEN is set in the "
                    "server environment."
                ),
            )
        scheme, _, presented = (authorization or "").partition(" ")
        # compare_digest, not ==: a plain comparison returns early on the first
        # differing byte and so leaks the token's length and prefix through
        # response timing. Encoded because compare_digest rejects non-ASCII str.
        if scheme.lower() != "bearer" or not presented or not hmac.compare_digest(
            presented.encode("utf-8"), expected.encode("utf-8")
        ):
            # Never echo any part of the expected token — that would turn the
            # rejection into an oracle.
            raise HTTPException(
                status_code=401, detail="Missing or invalid bearer token."
            )

    return dependency


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

    Gated by ``_require_api_token`` at the router level, so the handler below
    only ever runs for an authorized request and the bundle it assembles is
    byte-identical to the pre-gate version.
    """
    router = APIRouter(dependencies=[Depends(_require_api_token(settings))])

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
