# Phase 3e — Specialized Sub-Agents

**Date:** 2026-07-25
**Status:** Approved via brainstorming (user chose "specialized sub-agents / personas")

## Goal
Let Violet delegate a task to a named specialized agent — Researcher, Analyst, Writer, Coder —
each with its own model + system prompt. Config-driven and extensible (drop a JSON to add one).

## Decisions
- Agents are **config files** (`configs/agents/*.json`): `{id, name, description, model, base_url?,
  system_prompt, triggers?, priority?}`. Each has its OWN model (via OpenRouter).
- **Selection:** primarily explicit — the client sends `agent` on the chat request (a picker in the
  UI). Plus light rule-based auto-detection by triggers when no agent is explicitly chosen.
- **Precedence in the orchestrator:** mock → explicit agent → skill (artifact) → auto-detected agent
  → cascade → single provider. (Skills win over auto-detected agents so "make a chart" still charts.)
- Agents activate only when an agent key is configured (defaults to `OPENROUTER_API_KEY`); mock/offline
  requests never hit an agent.

## Starter agents
- `researcher` — deep research/reasoning (`deepseek/deepseek-r1-0528`).
- `analyst` — data analysis/interpretation (`deepseek/deepseek-chat-v3.1`).
- `writer` — long-form writing/copy (`nousresearch/hermes-4-70b`).
- `coder` — software engineering (`qwen/qwen3-coder`).

## Backend
- `agents/schema.py` (Agent), `agents/registry.py` (load + `detect`, priority-aware like skills),
  `agents/runner.py` (`AgentRunner.run(agent, messages)` → runs the agent's model with its system
  prompt via an OpenAI-compatible provider).
- `config.py`: `AGENTS_CONFIG_DIR`, `AGENT_BASE_URL`/`AGENT_API_KEY` (default OpenRouter).
- `schemas/chat.py`: `ChatRequest.agent`; `ChatResponse.agent` (which agent answered).
- `ChatOrchestrator`: routing precedence above; `main.py` builds the registry + runner.
- `GET /api/agents` → `{enabled, items:[{id,name,description,model}]}`.

## Frontend
- `lib/api.ts`: `AgentInfo`, `fetchAgents`, `sendChat(..., agent)`, `ChatResponse.agent`.
- `App`: `selectedAgent` state; passes it on send; shows the active agent.
- `SettingsModal`: an "Agent" selector (None / Researcher / Analyst / Writer / Coder).

## Testing
- Registry load + detect (priority/word-boundary, reused pattern). Runner uses an injected provider
  factory (no network in unit tests). Orchestrator precedence: explicit agent beats skill; skill beats
  auto-detected agent.
- Live smoke: pick Researcher → answer comes from the researcher model; auto-detect "research …".

## Out of scope (later)
Autonomous multi-step tool-use loops, agents invoking skills/each other, per-agent memory.
