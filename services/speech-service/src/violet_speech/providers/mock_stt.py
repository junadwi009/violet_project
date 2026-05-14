from __future__ import annotations

from violet_speech.schemas import ProviderHealth, Transcript


class MockSTTProvider:
    name = "mock"

    async def transcribe(self, text: str, language: str = "id") -> Transcript:
        return Transcript(
            text=text.strip(),
            language=language,
            confidence=1.0 if text.strip() else 0.0,
            provider=self.name,
        )

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            status="ok",
            detail="Mock STT accepts text and returns a transcript.",
        )

