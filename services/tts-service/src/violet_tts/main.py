from __future__ import annotations

from fastapi import FastAPI

from violet_tts.providers.mock_tts import MockTTSProvider
from violet_tts.schemas import AudioResult, ProviderHealth, SynthesizeRequest


def create_app() -> FastAPI:
    provider = MockTTSProvider()
    app = FastAPI(title="Violet TTS Service", version="0.1.0")

    @app.get("/health", response_model=ProviderHealth)
    async def health() -> ProviderHealth:
        return await provider.health()

    @app.post("/api/tts/synthesize", response_model=AudioResult)
    async def synthesize(request: SynthesizeRequest) -> AudioResult:
        return await provider.synthesize(
            request.text,
            voice=request.voice,
            language=request.language,
        )

    return app


app = create_app()

