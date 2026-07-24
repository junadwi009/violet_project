# Dockerize — portable two-service stack

- **Date:** 2026-07-24
- **Track:** infra / packaging
- **Branch:** main
- **Author:** Claude Code

## What
Containerized the app we built (assistant-core + web-client) into a portable Docker
Compose stack so the project runs anywhere with one command.

## Why
User wants to move the project between machines easily without local Python/Node setup.

## Files added
- `docker-compose.yml` — two services (`assistant-core`, `web`), SQLite named volume, one command.
- `services/assistant-core/Dockerfile` — python:3.11-slim, editable install (keeps `repo_root`
  resolution so `database/migrations` + `configs/` are found), uvicorn on :8000, healthcheck.
- `apps/web-client/Dockerfile` — multi-stage: node:20-alpine builds the Vite SPA →
  nginx:alpine serves it. Built with `VITE_API_BASE_URL=""` so the client uses same-origin paths.
- `apps/web-client/nginx.conf` — serves the SPA + reverse-proxies `/api` and `/health` to
  `assistant-core:8000` (same origin → no CORS, single published port).
- `.dockerignore` — excludes `.env`, `node_modules`, `dist`, `.git`, local data.
- `DOCKER.md` — usage + how to move to another machine + how to point at host Ollama.

## Ports / data
- Web app: `http://localhost:8080` (nginx). API direct: `http://localhost:8000` (+ `/docs`).
- SQLite persists in the `violet-data` named volume.
- `host.docker.internal` wired so the container can reach a host LLM server.

## Status
done — built and live-verified.

## Verification
- `docker compose build` → both images built (web 97.5MB, assistant-core 241MB).
- `docker compose up -d` → assistant-core **healthy**, web started on `depends_on: service_healthy`.
- Through the nginx proxy on :8080: `/` = HTTP 200; `/health`, `/api/providers` = 200;
  `POST /api/chat {"provider":"mock"}` → mock response (browser→nginx→backend path works).
- Built CSS served by nginx is correctly compiled (`:root,:host{` present, 0 raw `@theme`) —
  the earlier dev-server styling glitch does not occur in the container.
- Cleaned up leftover host dev servers (uvicorn :8000, vite :5173) to avoid port clashes.

## Notes / open for user
- Default LLM is **mock** on a clean machine (no `.env`). On this dev box, `docker compose`
  reads the repo-root `.env` for `${LLM_PROVIDER}` interpolation, so the server default shows
  `openai_compatible` ("Local", unhealthy without Ollama) — switch to **Mock** in the UI, start
  Ollama, or run with `LLM_PROVIDER=mock docker compose up`. On a moved machine without `.env`
  it defaults to mock automatically.
- speech-service / tts-service not containerized (mock-only, unused) — add later for Tracks 5/6.
- Docker files are not yet committed.
