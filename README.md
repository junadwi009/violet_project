# Violet AI

Violet AI is a local-first personal assistant project. This repository currently implements the Phase 1 backend MVP: a text chat API with personality configuration, an LLM provider adapter, SQLite-backed chat history, and memory-candidate placeholders that do not become permanent memory automatically.

## Phase 1 Scope

- FastAPI assistant-core service.
- `POST /api/chat` text chat endpoint.
- `GET /health` health endpoint.
- Memory candidate approval, rejection, edit, and delete endpoints.
- React web client for chat and memory review.
- Mock LLM provider as the default.
- OpenAI-compatible provider for Ollama, LM Studio, vLLM, or cloud endpoints when configured.
- JSON personality profile loading.
- SQLite schema for sessions, messages, memories, memory candidates, gesture events, and tool audit logs.
- Basic tests for core behavior.

Out of scope for this phase: webcam, microphone, TTS, avatar, internet research, autonomous tools, and VPS deployment.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

The default `.env.example` uses `LLM_PROVIDER=mock`, so no paid API key or local model server is required.

## Run

Start the backend:

```powershell
uvicorn violet_assistant.main:app --host 127.0.0.1 --port 8000
```

Then send a chat request:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/chat `
  -ContentType "application/json" `
  -Body '{"content":"Violet, remember that I prefer concise engineering updates.","personality_id":"violet.default"}'
```

If port `8000` is busy, use `8001` and set the web client API URL to match.

Start the web client:

```powershell
cd apps\web-client
npm install
$env:VITE_API_BASE_URL="http://127.0.0.1:8000"
npm run dev
```

Open the Vite URL printed in the terminal, usually `http://127.0.0.1:5173`.

## Memory Review

Candidate memories stay pending until approved:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/memory/candidates
```

Approve a candidate:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/memory/candidates/<candidate-id>/approve
```

Approved memories can be listed at:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/memory
```

## Use Ollama Or Another OpenAI-Compatible Endpoint

Set these values in `.env`:

```env
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen3.6:latest
LLM_API_KEY=
```

For a cloud OpenAI-compatible provider, place the API key in `LLM_API_KEY`. Do not commit real secrets.

## Test

```powershell
python -m pytest
```

## Safety Notes

- Permanent memory is not auto-saved.
- Memory-like statements become candidates for review.
- Provider selection is environment-driven.
- Risky tools are not implemented in Phase 1.
