from __future__ import annotations

from violet_assistant.config import Settings
from violet_assistant.vector.embeddings.base import EmbeddingProvider
from violet_assistant.vector.embeddings.mock_embedder import MockEmbedder
from violet_assistant.vector.embeddings.openai_compatible_embedder import (
    OpenAICompatibleEmbedder,
)


def create_embedder(settings: Settings) -> EmbeddingProvider:
    provider = settings.embed_provider.strip().lower()
    if provider in {"mock", "none", ""}:
        return MockEmbedder()
    if provider in {"openai_compatible", "ollama", "openai"}:
        return OpenAICompatibleEmbedder(
            base_url=settings.embed_base_url,
            model=settings.embed_model,
            api_key=settings.embed_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    raise ValueError(f"Unsupported EMBED_PROVIDER={settings.embed_provider!r}")
