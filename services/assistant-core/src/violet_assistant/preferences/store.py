from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from violet_assistant.config import Settings

# Editable keys map to a validator plus the settings group they render under. NO
# secrets here — API keys, base URLs, DB paths, and the ALLOW_* safety toggles
# stay in the frozen Settings / .env.


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


def _choice(*allowed: str) -> Callable[[Any], bool]:
    options = set(allowed)
    return lambda value: value in options


@dataclass(frozen=True)
class PrefSpec:
    validate: Callable[[Any], bool]
    group: str


GROUPS: tuple[str, ...] = (
    "general",
    "appearance",
    "model",
    "behavior",
    "voice",
    "knowledge",
)


EDITABLE_KEYS: dict[str, PrefSpec] = {
    # general
    "ui_mode": PrefSpec(_choice("user", "developer"), "general"),
    "default_personality": PrefSpec(_is_str, "general"),
    "default_provider": PrefSpec(_is_str, "general"),
    # appearance
    "theme": PrefSpec(_choice("light", "dark", "system"), "appearance"),
    "ui_density": PrefSpec(_choice("cozy", "compact"), "appearance"),
    "font_scale": PrefSpec(_num(0.875, 1.25), "appearance"),
    "accent": PrefSpec(
        _choice("violet", "indigo", "teal", "amber", "rose"), "appearance"
    ),
    # model
    "llm_model": PrefSpec(_is_str, "model"),
    "temperature": PrefSpec(_num(0.0, 2.0), "model"),
    # Model IDENTIFIERS only — the matching *_base_url / *_api_key stay frozen in Settings.
    "persona_model": PrefSpec(_is_str, "model"),
    "technical_model": PrefSpec(_is_str, "model"),
    "artifact_model": PrefSpec(_is_str, "model"),
    "vision_model": PrefSpec(_is_str, "model"),
    "agent_default_model": PrefSpec(_is_str, "model"),
    # behavior
    "memory_require_approval": PrefSpec(_is_bool, "behavior"),
    "memory_auto_save": PrefSpec(_is_bool, "behavior"),
    "web_search_enabled": PrefSpec(_is_bool, "behavior"),
    "canvas_enabled": PrefSpec(_is_bool, "behavior"),
    # `web_search_model` is a web-search knob, not a model identity — it lives
    # next to `web_search_enabled` in the UI (BehaviorPanel) and its dot/reset
    # need to match that, so it groups with behavior rather than model.
    "web_search_model": PrefSpec(_is_str, "behavior"),
    # voice
    "voice_lang": PrefSpec(_is_str, "voice"),
    "voice_name": PrefSpec(_is_str, "voice"),
    "voice_rate": PrefSpec(_num(0.5, 2.0), "voice"),
    "voice_pitch": PrefSpec(_num(0.0, 2.0), "voice"),
    "auto_speak": PrefSpec(_is_bool, "voice"),
    # knowledge
    "knowledge_auto_sync": PrefSpec(_is_bool, "knowledge"),
}


def keys_in_group(group: str) -> list[str]:
    if group not in GROUPS:
        raise KeyError(group)
    return [key for key, spec in EDITABLE_KEYS.items() if spec.group == group]


def _defaults(settings: Settings) -> dict[str, Any]:
    return {
        "llm_model": settings.llm_model,
        "temperature": settings.default_temperature,
        "memory_require_approval": settings.memory_require_approval,
        "memory_auto_save": settings.memory_auto_save,
        "web_search_enabled": False,
        "web_search_model": settings.web_search_model,
        "persona_model": settings.persona_model,
        "technical_model": settings.technical_model,
        "artifact_model": settings.artifact_model,
        "vision_model": settings.vision_model,
        "agent_default_model": settings.agent_default_model,
        "canvas_enabled": True,
        "default_personality": "violet.default",
        "default_provider": settings.llm_provider,
        "ui_mode": "user",
        "knowledge_auto_sync": settings.knowledge_auto_sync,
        "theme": "system",
        "ui_density": "cozy",
        "font_scale": 1.0,
        "accent": "violet",
        "voice_lang": "id-ID",
        "voice_name": "",
        "voice_rate": 1.0,
        "voice_pitch": 1.0,
        "auto_speak": False,
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

    def reset(self, keys: list[str]) -> dict[str, Any]:
        """Drop the named overrides so ``effective`` falls back to Settings."""
        for key in keys:
            if key not in EDITABLE_KEYS:
                raise ValueError(f"unknown or non-editable key: {key}")
        current = {
            key: value for key, value in self._load().items() if key not in keys
        }
        current = {key: value for key, value in current.items() if key in EDITABLE_KEYS}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        return current

    def patch(self, changes: dict[str, Any]) -> dict[str, Any]:
        for key, value in changes.items():
            if key not in EDITABLE_KEYS:
                raise ValueError(f"unknown or non-editable key: {key}")
            if not EDITABLE_KEYS[key].validate(value):
                raise ValueError(f"invalid value for {key}: {value!r}")
        current = self._load()
        current.update(changes)
        current = {key: value for key, value in current.items() if key in EDITABLE_KEYS}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        return current
