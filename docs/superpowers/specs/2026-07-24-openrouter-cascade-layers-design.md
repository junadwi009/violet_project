# OpenRouter Wiring + Cascade Model Layers — Design Spec

**Date:** 2026-07-24
**Status:** Approved via brainstorming
**Scope:** Phase 1 (wire OpenRouter) + Phase 2 (cascade router). Phase 3 (skills/tools) is separate.

## Goals
Wire OpenRouter as a provider and add a token-efficient multi-layer model architecture:
a steerable/low-refusal **persona layer** (private-facing) that delegates heavy technical work to a
**technical layer** on demand.

## Decisions (from brainstorming)
1. **Privacy:** prepare for both a local host and the cloud API; use OpenRouter for development now.
   Each layer's endpoint is configurable, so the persona layer can move to a local Ollama host later
   with an env change (no code change).
2. **Models (live-verified on the key, swappable via env):**
   - Persona: `nousresearch/hermes-4-70b` (steerable, low-refusal, ~$0.13/$0.40 per 1M).
   - Technical: `deepseek/deepseek-chat-v3.1` (~$0.25/$0.95). `deepseek/deepseek-r1-0528` optional for
     hard reasoning.
3. **Routing:** cascade + delegate-on-demand (persona-first; self-delegates heavy sub-tasks).
4. **Opt-in:** `LLM_ROUTER=single` (default, keeps mock/offline working) vs `cascade`.
5. **Secret:** `OPENROUTER_API_KEY` in `.env` (git-ignored), never committed; user to rotate after setup.

## Architecture
Layer = `{base_url, model, api_key}` built from env:
- **persona**: `PERSONA_BASE_URL` (default OpenRouter), `PERSONA_MODEL`, `PERSONA_API_KEY`
  (defaults to `OPENROUTER_API_KEY`).
- **technical**: `TECHNICAL_BASE_URL`, `TECHNICAL_MODEL`, `TECHNICAL_API_KEY` (defaults to `OPENROUTER_API_KEY`).

`CascadeResponder.respond(messages, base_options)`:
1. Call the **persona** model with the existing system prompt + a small delegation instruction:
   "If the request needs heavy calculation/code/technical reasoning, reply with exactly
   `DELEGATE: <focused subtask>` and nothing else."
2. If the reply starts with `DELEGATE:`, extract the subtask, call the **technical** model once with a
   focused prompt (subtask + minimal context), then call the **persona** model again to compose the
   final in-character answer using the technical result. Cap at one delegation (no loops).
3. Otherwise return the persona reply directly.
Returns `LLMResponse(text, emotion)` plus metadata (models used, delegated flag) for logging/UI.

Efficiency: most turns = 1 persona call; delegation = 3 calls only when genuinely needed. Cheap
prices + capped history keep tokens low. (Optional future: a rule-based pre-router to skip step 1 for
obvious technical prompts.)

## Integration
- New `OpenAICompatibleProvider` gains optional default headers (OpenRouter's `HTTP-Referer`/`X-Title`).
- `ChatOrchestrator`: when `LLM_ROUTER=cascade` and the request isn't the mock provider, use
  `CascadeResponder` instead of the single `provider.chat()`. Mock (offline) still honored via the
  provider switch.
- `config.py`: `openrouter_api_key`, `openrouter_base_url`, `llm_router`, persona/technical layer vars.
- `GET /api/providers` (or a new `/api/router/info`) reports router mode + layer models for the UI.

## Frontend
- Settings modal shows the active router mode + the persona/technical model ids (read-only readout).
  Chat flow unchanged.

## Testing
- Unit: cascade with fake providers — no-delegate path returns persona text; delegate path calls
  technical then persona-compose; delegation capped at one.
- Config: layer construction + env defaulting to `OPENROUTER_API_KEY`.
- Live smoke (real key, minimal tokens): a plain persona turn + a delegating turn (e.g. a calculation).

## Out of scope (later)
Phase 3 skills/tools (calculator/code/search + curated prompt-skills); local-host persona swap
(supported by config, not exercised now); streaming.
