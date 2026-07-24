from __future__ import annotations

from violet_assistant.config import Settings
from violet_assistant.llm.base import LLMProvider
from violet_assistant.llm.factory import OPENAI_COMPATIBLE_PROVIDERS
from violet_assistant.llm.mock_provider import MockLLMProvider
from violet_assistant.llm.openai_compatible_provider import OpenAICompatibleProvider


MOCK = "mock"
OPENAI_COMPATIBLE = "openai_compatible"

PROVIDER_LABELS = {
    MOCK: "Mock (offline)",
    OPENAI_COMPATIBLE: "Local / OpenAI-compatible",
}


def default_provider_name(settings: Settings) -> str:
    """Map the configured ``LLM_PROVIDER`` onto a registry key."""
    if settings.llm_provider in OPENAI_COMPATIBLE_PROVIDERS:
        return OPENAI_COMPATIBLE
    return MOCK


def build_provider_registry(settings: Settings) -> dict[str, LLMProvider]:
    """Return the switchable set of providers, keyed by public id.

    Always exposes ``mock`` (zero-config, offline) and ``openai_compatible`` (built from
    ``LLM_BASE_URL`` / ``LLM_API_KEY``). The client selects one per chat request; if the
    selected provider is unreachable the request surfaces that error rather than silently
    falling back, so the switch is honest.
    """
    return {
        MOCK: MockLLMProvider(),
        OPENAI_COMPATIBLE: OpenAICompatibleProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        ),
    }


def describe_providers(settings: Settings) -> dict:
    """Payload for ``GET /api/providers``."""
    active = default_provider_name(settings)
    registry = build_provider_registry(settings)
    return {
        "active": active,
        "items": [
            {
                "id": name,
                "label": PROVIDER_LABELS.get(name, name),
                "active": name == active,
            }
            for name in registry
        ],
    }
