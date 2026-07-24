# Phase 3e — Specialized sub-agents

- **Date:** 2026-07-25
- **Track:** agents / delegation
- **Branch:** main
- **Author:** Claude Code

## What
Added named specialized sub-agents Violet can delegate a task to, each with its own OpenRouter model
and system prompt. Config-driven and extensible. Also fixed a skill-routing bug (priority).

## Sub-agents (configs/agents/*.json)
- `researcher` — deep research/reasoning (`deepseek/deepseek-r1-0528`).
- `analyst` — data analysis/interpretation (`deepseek/deepseek-chat-v3.1`).
- `writer` — long-form/professional writing (`nousresearch/hermes-4-70b`).
- `coder` — software engineering (`qwen/qwen3-coder`).

## Backend
- `agents/`: `schema.py` (Agent: id/name/model/base_url?/system_prompt/triggers/priority),
  `registry.py` (load + `get` + `detect`, word-boundary + priority), `runner.py`
  (`AgentRunner.run` — the agent's model + system prompt over the conversation).
- `config.py`: `AGENTS_CONFIG_DIR`, `AGENT_BASE_URL/API_KEY` (default OpenRouter). Agents active only
  when a key is present.
- `schemas/chat.py`: `ChatRequest.agent` (explicit selection) + `ChatResponse.agent` (who answered).
- `ChatOrchestrator` routing precedence: mock → explicit agent → skill → auto-detected agent →
  cascade → provider. `GET /api/agents`; `main.py` builds the registry + runner.

## Frontend
- `lib/api.ts`: `AgentInfo`, `fetchAgents`, `sendChat(..., agent)`, `ChatResponse.agent`.
- `SettingsModal`: "Delegate to agent" selector (Violet / Researcher / Analyst / Writer / Coder).
- `WorkspaceHeader`: shows a `↳ <Agent>` chip when an agent is active. `App` passes the selection.

## Interfaces / contracts
- `ChatRequest.agent`, `ChatResponse.agent` (additive). New `GET /api/agents`. `Settings` gained
  agent fields (defaulted). No breaking changes.

## Status
done — tests green, live-verified.

## Verification
- `python -m pytest` → **62 passed** (+7: registry get/detect, runner model+prompt, orchestrator
  precedence incl. explicit>skill>detected and mock bypass). Frontend `npm run build` clean.
- Live (real key): `/api/agents` → 4 agents on their own models. Explicit `agent=coder` →
  `response.agent=coder` with Python code. Auto-detect "research the coffee market" →
  `response.agent=researcher` with structured analysis.

## Also
Fixed skill routing with a `priority` field (file-output skills win explicit docx/word/pptx requests);
commit d961774.

## Next
Autonomous multi-step tool-use loops; agents invoking skills (orchestrator agent); per-agent memory;
letting the persona hand off mid-conversation (HANDOFF marker).
