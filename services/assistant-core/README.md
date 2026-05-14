# Assistant Core

Assistant Core is the Phase 1 backend service for Violet AI.

## Endpoints

- `GET /health`
- `POST /api/chat`
- `GET /api/memory/candidates`

## Local Run

From the repository root:

```powershell
python -m pip install -e ".[dev]"
uvicorn violet_assistant.main:app --host 127.0.0.1 --port 8000
```

The service defaults to `LLM_PROVIDER=mock`, which is deterministic and offline-friendly.

