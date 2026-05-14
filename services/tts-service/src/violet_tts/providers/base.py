from __future__ import annotations

from typing import Protocol

from violet_tts.schemas import AudioResult, ProviderHealth


class TTSProvider(Protocol):
    name: str

    async def synthesize(
        self, text: str, voice: str = "default", language: str = "id"
    ) -> AudioResult:
        """Return synthesized speech or a mock result."""

    async def health(self) -> ProviderHealth:
        """Return provider health."""

