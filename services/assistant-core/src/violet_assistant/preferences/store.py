from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from violet_assistant.config import Settings

# Editable keys map to a validator. NO secrets here — API keys, base URLs, DB
# paths, and the ALLOW_* safety toggles stay in the frozen Settings / .env.


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _num(lo: float, hi: float) -> Callable[[Any], bool]:
    return (
        lambda value: isinstance(value, (int, float))
        and not isinstance(value, bool)
        and lo <= value <= hi
    )


def _is_str(value: Any) -> bool:
    return isinstance(value, str) and len(value) <= 200


EDITABLE_KEYS: dict[str, Callable[[Any], bool]] = {
    "llm_model": _is_str,
    "temperature": _num(0.0, 2.0),
    "memory_require_approval": _is_bool,
    "memory_auto_save": _is_bool,
    "web_search_enabled": _is_bool,
    "web_search_model": _is_str,
    "canvas_enabled": _is_bool,
    "default_personality": _is_str,
    "default_provider": _is_str,
    "ui_mode": lambda v: v in {"user", "developer"},
    "knowledge_auto_sync": _is_bool,
}


def _defaults(settings: Settings) -> dict[str, Any]:
    return {
        "llm_model": settings.llm_model,
        "temperature": settings.default_temperature,
        "memory_require_approval": settings.memory_require_approval,
        "memory_auto_save": settings.memory_auto_save,
        "web_search_enabled": False,
        "web_search_model": settings.web_search_model,
        "canvas_enabled": True,
        "default_personality": "violet.default",
        "default_provider": settings.llm_provider,
        "ui_mode": "user",
        "knowledge_auto_sync": settings.knowledge_auto_sync,
    }


class PreferencesStore:
    """JSON-backed overrides merged over Settings defaults. Pure I/O, no network."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, OSError):
            return {}

    def overridden(self) -> list[str]:
        return [key for key in self._load() if key in EDITABLE_KEYS]

    def defaults(self, settings: Settings) -> dict[str, Any]:
        return _defaults(settings)

    def effective(self, settings: Settings) -> dict[str, Any]:
        values = _defaults(settings)
        for key, value in self._load().items():
            if key in EDITABLE_KEYS:
                values[key] = value
        return values

    def patch(self, changes: dict[str, Any]) -> dict[str, Any]:
        for key, value in changes.items():
            if key not in EDITABLE_KEYS:
                raise ValueError(f"unknown or non-editable key: {key}")
            if not EDITABLE_KEYS[key](value):
                raise ValueError(f"invalid value for {key}: {value!r}")
        current = self._load()
        current.update(changes)
        current = {key: value for key, value in current.items() if key in EDITABLE_KEYS}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        return current
