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
- Sessions/candidates (SQLite) persist in the `violet-data` named volume across restarts.
- **Approved memories are markdown files** in the host folder **`./memory`** (bind-mounted to
  `/app/memory`). Open/edit/delete them directly, or point that folder at a VPS mount or a
  Google-Drive-synced folder to sync your memory to the cloud. See "Memory storage" below.

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

## Memory storage
Approved memories are Claude-style markdown files (one per fact + a `MEMORY.md` index), managed
as a directory so they're portable and human-editable.

- **Local folder (default):** `./memory` on the host, bind-mounted into the container. Edit the
  `.md` files directly; changes are read back by the app.
- **VPS:** run the stack on the VPS — `./memory` lives on the server. Or bind-mount a different
  path by editing the `web`/`assistant-core` volume in `docker-compose.yml`.
- **Google Drive:** point the mount at a Drive-synced / rclone folder, e.g. change the compose
  line to `- /path/to/GoogleDrive/violet-memory:/app/memory`. Files then sync to Drive
  automatically — no API keys needed. (A native Drive-API backend can be added later behind the
  same `MEMORY_BACKEND` switch.)
- Switch back to the DB-backed store with `MEMORY_BACKEND=sqlite docker compose up`.

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
