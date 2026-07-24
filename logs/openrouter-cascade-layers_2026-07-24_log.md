# OpenRouter wiring + cascade model layers

- **Date:** 2026-07-24
- **Track:** LLM / model architecture (Phase 1 + 2)
- **Branch:** main
- **Author:** Claude Code

## What
Wired OpenRouter and added a token-efficient two-layer model architecture: a steerable/low-refusal
**persona layer** (private-facing) that delegates heavy technical sub-tasks to a **technical layer**
on demand (cascade + delegate-on-demand). Design:
`docs/superpowers/specs/2026-07-24-openrouter-cascade-layers-design.md`.

## Why
User wants an uncensored, personality-adjustable front for private knowledge, plus extra layers for
technical work, with efficient tokens. Hybrid-ready: each layer's endpoint is configurable so the
persona layer can later run on a local host while the technical layer uses the API.

## Models (live-verified on the key; swappable via env)
- Persona: `nousresearch/hermes-4-70b` (~$0.13/$0.40 per 1M) — steerable, low-refusal.
- Technical: `deepseek/deepseek-chat-v3.1` (~$0.25/$0.95). `deepseek-r1-0528` optional for hard reasoning.

## Backend
- `config.py` — `LLM_ROUTER` (default `single`), `OPENROUTER_API_KEY/BASE_URL`, and per-layer
  `PERSONA_*` / `TECHNICAL_*` (base_url/model/api_key, each defaulting to the OpenRouter key). New
  fields have dataclass defaults so existing manual `Settings(...)` construction is unchanged.
- `orchestrator/cascade.py` — `CascadeResponder`: persona-first; on `DELEGATE: <subtask>` calls the
  technical layer once, then persona composes the final in-character answer. One delegation, no loops.
  `LayerConfig`, `build_layer_configs`. Injectable `provider_factory` for testing.
- `OpenAICompatibleProvider` — optional `default_headers` (OpenRouter `HTTP-Referer`/`X-Title`).
- `ChatOrchestrator` — uses the cascade when `LLM_ROUTER=cascade` and the request isn't `mock`
  (mock/offline still honored via the provider switch).
- `main.py` — builds the cascade when enabled. `registry.describe_providers` now includes a `router`
  object (mode + persona/technical models) in `GET /api/providers`.

## Frontend / infra
- `lib/api.ts` `RouterInfo` + `ProvidersResponse.router`; App stores it; SettingsModal shows a
  "Routing · cascade" readout with the persona/technical model ids.
- `.env.example` documents the new vars (names only). Real key appended to git-ignored `.env`.
- `docker-compose.yml` passes `LLM_ROUTER`/`OPENROUTER_API_KEY`/models at runtime (never baked).

## Interfaces / contracts
- `Settings` gained 9 routing fields (all with defaults). `ChatOrchestrator` gained optional
  `cascade`. `GET /api/providers` payload gained `router`. No breaking changes.

## Status
done — tests green, live-verified against real OpenRouter.

## Verification
- `python -m pytest` → **35 passed** (+3 cascade tests: no-delegate, delegate→technical→compose,
  delegation capped at one). `npm run build` clean.
- Live (local uvicorn, cascade, real key):
  - `GET /api/providers` → `router.mode=cascade`, persona=hermes-4-70b, technical=deepseek-chat-v3.1.
  - Plain turn → Hermes answered in-character as Violet (Indonesian).
  - `48273 × 91647` → **4424075631** (exact) via delegation to the technical layer.

## Security
- OpenRouter key kept only in git-ignored `.env`; never committed or echoed. **User advised to rotate**
  the key (it was shared in plaintext).

## Next (Phase 3)
Skills/tools layer (calculator/code/search + curated prompt-skills from Claude/ChatGPT/community);
move persona layer to a local Ollama host for full privacy; optional rule-based pre-router; streaming.
