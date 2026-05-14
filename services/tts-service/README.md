# TTS Service

Phase 2 starts with a mock TTS service. It exposes the adapter shape and health endpoint without requiring Piper, voice cloning, or audio model downloads.

## Endpoints

- `GET /health`
- `POST /api/tts/synthesize`

The mock provider returns text metadata and no audio payload.

