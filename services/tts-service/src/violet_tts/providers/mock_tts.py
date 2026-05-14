from __future__ import annotations

from violet_tts.schemas import AudioResult, ProviderHealth


class MockTTSProvider:
    name = "mock"

    async def synthesize(
        self, text: str, voice: str = "default", language: str = "id"
    ) -> AudioResult:
        return AudioResult(
            text=text,
            voice=voice,
            language=language,
            audio_base64=None,
            provider=self.name,
        )

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            status="ok",
            detail="Mock TTS returns text metadata without audio.",
        )

