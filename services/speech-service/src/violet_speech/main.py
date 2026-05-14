from __future__ import annotations

from fastapi import FastAPI

from violet_speech.providers.mock_stt import MockSTTProvider
from violet_speech.schemas import ProviderHealth, TranscribeRequest, Transcript


def create_app() -> FastAPI:
    provider = MockSTTProvider()
    app = FastAPI(title="Violet Speech Service", version="0.1.0")

    @app.get("/health", response_model=ProviderHealth)
    async def health() -> ProviderHealth:
        return await provider.health()

    @app.post("/api/stt/transcribe", response_model=Transcript)
    async def transcribe(request: TranscribeRequest) -> Transcript:
        return await provider.transcribe(request.text, language=request.language)

    return app


app = create_app()

