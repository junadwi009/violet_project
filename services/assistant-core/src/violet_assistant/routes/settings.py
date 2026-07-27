from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from violet_assistant.config import Settings
from violet_assistant.preferences.store import PreferencesStore, keys_in_group


class SettingsPatch(BaseModel):
    # Accept an arbitrary partial of editable keys; the store validates them.
    model_config = {"extra": "allow"}


class ResetRequest(BaseModel):
    group: str | None = None
    keys: list[str] | None = None


# Safety-relevant settings shown read-only in the UI. An explicit allowlist, never
# a filter over Settings — a filter silently starts leaking the moment someone adds
# a field whose name it did not anticipate.
LOCKED_KEYS: tuple[str, ...] = (
    "llm_provider",
    "agent_tools_enabled",
    "allow_shell_tools",
    "allow_email_tools",
    "allow_file_delete",
    "require_confirmation_for_risky_tools",
    "tool_confirm_threshold",
    "max_tool_iterations",
)


def create_settings_router(store: PreferencesStore, settings: Settings) -> APIRouter:
    router = APIRouter()

    def _payload() -> dict:
        return {
            "values": store.effective(settings),
            "defaults": store.defaults(settings),
            "overridden": store.overridden(),
            "locked": {key: getattr(settings, key) for key in LOCKED_KEYS},
        }

    @router.get("/api/settings")
    async def get_settings() -> dict:
        return _payload()

    @router.patch("/api/settings")
    async def patch_settings(patch: SettingsPatch) -> dict:
        try:
            store.patch(patch.model_dump(exclude_unset=True))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _payload()

    @router.post("/api/settings/reset")
    async def reset_settings(payload: ResetRequest) -> dict:
        if (payload.group is None) == (payload.keys is None):
            raise HTTPException(
                status_code=422, detail="provide exactly one of 'group' or 'keys'"
            )
        try:
            targets = (
                keys_in_group(payload.group)
                if payload.group is not None
                else list(payload.keys or [])
            )
            store.reset(targets)
        except KeyError as exc:
            raise HTTPException(
                status_code=422, detail=f"unknown group: {payload.group}"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _payload()

    return router
