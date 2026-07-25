# Wire agent loop into chat + resume route

- **Date:** 2026-07-26
- **Track:** 1 Chat (agent tool loop, Task 6)
- **Branch:** feat/agent-tool-loop
- **Author:** Claude

## What
`ChatResponse` gained `tool_trace` and `agent_run_id`, and finally populates
`tool_requests` (unused since the original blueprint). `ChatOrchestrator` takes an
`agent_loop` and routes **both** agent branches (explicit and auto-detected)
through it when `AGENT_TOOLS_ENABLED` is on, persisting a paused run via
`store.create_agent_run`. New `routes/agent_runs.py` exposes
`GET /api/agent-runs/{id}` and `POST /api/agent-runs/{id}/resume`. `main.py`
builds the tool registry + loop (with `store.add_tool_audit_log` as the audit
sink) only when the flag is set.

## Why
Connect the loop to chat and give the UI a way to approve or reject a gated call.

## Files touched
- `services/assistant-core/src/violet_assistant/schemas/chat.py`
- `services/assistant-core/src/violet_assistant/orchestrator/chat_orchestrator.py` (SHARED SEAM)
- `services/assistant-core/src/violet_assistant/routes/agent_runs.py` (new)
- `services/assistant-core/src/violet_assistant/main.py` (SHARED SEAM)
- `services/assistant-core/tests/test_agent_run_routes.py` (new)
- `services/assistant-core/tests/test_chat_orchestrator.py` (pause test)

## Interfaces / contracts changed
- `ChatResponse.tool_trace`, `ChatResponse.agent_run_id`; `tool_requests` now real.
- `ChatOrchestrator(..., agent_loop=None)`.
- New routes `GET /api/agent-runs/{run_id}`, `POST /api/agent-runs/{run_id}/resume`
  (404 unknown run / unknown tool_call_id, 409 not-paused or tools disabled).

## Status
done

## Verification
`python -m pytest -q` → **184 passed**.
Boot check: both routes present in the OpenAPI schema, and
`agent_tools_enabled` is **False** by default — with the flag unset the agent
path is byte-identical to before (the loop clause is skipped and the existing
`agent_runner.run` branch handles it).

## Next
Task 7: frontend trace + approval card.
