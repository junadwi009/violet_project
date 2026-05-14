from __future__ import annotations

from typing import Protocol

from violet_speech.schemas import ProviderHealth, Transcript


class STTProvider(Protocol):
    name: str

    async def transcribe(self, text: str, language: str = "id") -> Transcript:
        """Return a transcript for supplied audio or mock text."""

    async def health(self) -> ProviderHealth:
        """Return provider health."""

