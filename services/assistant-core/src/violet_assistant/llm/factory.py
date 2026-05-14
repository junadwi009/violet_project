from __future__ import annotations

from violet_assistant.config import Settings
from violet_assistant.llm.base import LLMProvider
from violet_assistant.llm.mock_provider import MockLLMProvider
from violet_assistant.llm.openai_compatible_provider import OpenAICompatibleProvider


OPENAI_COMPATIBLE_PROVIDERS = {
    "ollama",
    "lmstudio",
    "llama_cpp",
    "vllm",
    "openai_compatible",
    "cloud_fallback",
}


def create_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockLLMProvider()

    if settings.llm_provider in OPENAI_COMPATIBLE_PROVIDERS:
        return OpenAICompatibleProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    supported = ["mock", *sorted(OPENAI_COMPATIBLE_PROVIDERS)]
    raise ValueError(
        f"Unsupported LLM_PROVIDER={settings.llm_provider!r}. "
        f"Supported values: {', '.join(supported)}"
    )

