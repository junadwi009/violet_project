from __future__ import annotations

from violet_assistant.config import Settings
from violet_assistant.preferences.store import PreferencesStore


class ModelResolver:
    """Resolve a model-id preference at call time, falling back to ``Settings``.

    Components hold this instead of a frozen model string so that editing a model
    id in the settings UI takes effect on the next request rather than the next
    restart. Deliberately does not cache — ``PreferencesStore.effective`` re-reads
    a small JSON file, which is cheap relative to the LLM call it precedes.
    """

    def __init__(self, preferences: PreferencesStore | None, settings: Settings) -> None:
        self._preferences = preferences
        self._settings = settings

    def resolve(self, key: str) -> str:
        fallback = getattr(self._settings, key)
        if self._preferences is None:
            return fallback
        value = self._preferences.effective(self._settings).get(key)
        # A blank override means "unset" — never send model="" to a provider.
        if isinstance(value, str) and value.strip():
            return value
        return fallback
