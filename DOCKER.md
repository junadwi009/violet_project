# Running Violet with Docker

Portable, self-contained run of the Violet assistant — no local Python/Node setup needed.
Containerizes the two services we built and wired: **assistant-core** (FastAPI) and the
**web-client** (built to static, served by nginx which reverse-proxies the API).

## Prerequisites
- Docker + Docker Compose v2 (`docker compose version`).

## Start

```bash
docker compose up --build
```

Then open **http://localhost:8080**.

- Web app: http://localhost:8080 (nginx serves the SPA and proxies `/api` → backend)
- API direct (optional): http://localhost:8000 — e.g. http://localhost:8000/docs
- Data (SQLite) persists in the `violet-data` named volume across restarts.

Stop:

```bash
docker compose down          # keep data
docker compose down -v       # also delete the SQLite volume
```

## Choosing the LLM engine
The default is the offline **mock** provider — the app works fully with no model server.
You can switch the engine live in the UI (Settings → AI engine), or set the server default:

```bash
# Use a local Ollama running on the host machine:
LLM_PROVIDER=ollama LLM_BASE_URL=http://host.docker.internal:11434/v1 LLM_MODEL=llama3 \
  docker compose up --build
```

`host.docker.internal` is already wired in `docker-compose.yml` so the container can reach a
model server running on your host.

## Moving the project to another machine
1. Copy the repo (or just: `pyproject.toml`, `services/`, `database/`, `configs/`, `apps/web-client/`, `docker-compose.yml`, and the two `Dockerfile`s + `nginx.conf`).
2. On the target machine: `docker compose up --build`.

No secrets are baked into the images — the local `.env` is excluded via `.dockerignore`.
Configuration is passed at runtime through environment variables.

## What's in the images
| Service | Base | Serves |
|---|---|---|
| `assistant-core` | `python:3.11-slim` | uvicorn on `:8000` (chat, memory, providers, sessions) |
| `web` | `node:20-alpine` build → `nginx:alpine` | SPA on `:80` (published `:8080`) + `/api` proxy |

Out of scope (mock-only, not wired): `speech-service`, `tts-service`. They can be added as
extra compose services later if real STT/TTS lands (Tracks 5/6).
