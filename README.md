# Violet AI

Violet AI is a local-first personal assistant project. This repository currently implements the Phase 1 text MVP, the first safe Phase 2 voice scaffolding, and a Phase 3 avatar placeholder that stops before requiring a manual VRM asset.

## Current Scope

- FastAPI assistant-core service.
- `POST /api/chat` text chat endpoint.
- `GET /health` health endpoint.
- Memory candidate approval, rejection, edit, and delete endpoints.
- React web client for chat and memory review.
- Phase 2 mock STT/TTS service scaffolding.
- Browser speech input and speech output controls in the web client when supported.
- Phase 3 avatar placeholder with state and emotion mapping.
- Mock LLM provider as the default.
- OpenAI-compatible provider for Ollama, LM Studio, vLLM, or cloud endpoints when configured.
- JSON personality profile loading.
- Personality selector with `violet.default` and `violet.devoted_strategist`.
- SQLite schema for sessions, messages, memories, memory candidates, gesture events, and tool audit logs.
- Basic tests for core behavior.

Still out of scope: real voice cloning, real STT model downloads, real Piper/XTTS/OpenVoice/Fish setup, real VRM rendering, webcam gesture recognition, internet research, autonomous tools, and VPS deployment.

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

The web client includes browser-native speech controls. Speech input asks for microphone access only when you press the microphone button. Speech output uses the browser speech synthesis API and does not call a paid service.

## Phase 3 Avatar Placeholder

The web client now shows a local placeholder avatar that changes state while Violet is idle, listening, thinking, speaking, confirming, or handling an error.

The next avatar step requires a manual asset:

```text
apps/web-client/public/avatar/violet.vrm
```

Use `configs/avatar/avatar.example.json` as the intended config shape. Do not commit private or licensed avatar files unless you are sure they are allowed to be public in this repo.

## Phase 2 Mock Voice Services

Run the mock STT service:

```powershell
uvicorn violet_speech.main:app --host 127.0.0.1 --port 9090
```

Run the mock TTS service:

```powershell
uvicorn violet_tts.main:app --host 127.0.0.1 --port 8020
```

Smoke test STT:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:9090/api/stt/transcribe `
  -ContentType "application/json" `
  -Body '{"text":"Halo Violet","language":"id"}'
```

Smoke test TTS:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8020/api/tts/synthesize `
  -ContentType "application/json" `
  -Body '{"text":"Halo Violet","language":"id","voice":"default"}'
```

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

## Personalities

Personality profiles live in:

```text
configs/personality/
```

The included `violet.devoted_strategist` profile is a safe interpretation of the Devoted Strategist concept: deeply loyal and elegant toward Aru, strategically sharp toward markets and competitors, but still bound by truthfulness, consent, and lawful conduct.

List available profiles:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/personalities
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
