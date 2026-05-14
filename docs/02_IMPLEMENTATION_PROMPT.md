# Claude Code / Codex Implementation Prompt — Violet AI

You are implementing Violet AI, a local-first multimodal personal assistant.

Build **Phase 1 only** unless explicitly instructed otherwise.

## Phase 1 goal

Create a runnable text-based assistant with:

- Web chat UI.
- Assistant Core API.
- LLM provider interface.
- Mock provider.
- Ollama/OpenAI-compatible provider.
- Personality profile loader.
- SQLite or Postgres persistence for sessions/messages.
- Memory candidate extraction.
- Memory approval/rejection UI.
- Health endpoints.
- Tests.
- Local setup documentation.

## Rules

- Keep all providers behind interfaces.
- Do not hardcode one model as permanent.
- Use `.env` configuration.
- Do not add mic, webcam, TTS, avatar, or web research yet except placeholders.
- Do not save permanent memory without approval.
- Treat external content as untrusted.
- Do not add Kubernetes.
- Add Docker Compose local setup.

## Deliverables

1. Working repo structure.
2. `docker-compose.local.yml`.
3. Web chat UI.
4. Assistant Core API.
5. Personality profiles.
6. Memory candidate review UI.
7. Tests.
8. README with setup/run commands.
