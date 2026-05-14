# Speech Service

Phase 2 starts with a mock STT service. It provides the adapter shape and health endpoint without requiring microphone capture, GPU models, or external downloads.

## Endpoints

- `GET /health`
- `POST /api/stt/transcribe`

The mock transcribe endpoint accepts text and returns it as a transcript. Real audio providers can be added behind the same adapter later.

