# Agent tool loop — end-to-end verification

- **Date:** 2026-07-26
- **Track:** cross-cutting (agent tool loop, final)
- **Branch:** feat/agent-tool-loop
- **Author:** Claude

## What
End-to-end verification of the whole loop against a live backend and a real LLM
(OpenRouter, hermes-4-70b) with `AGENT_TOOLS_ENABLED=true`,
`TOOL_CONFIRM_THRESHOLD=medium`, `RAG_PROVIDER=vector`.

## Verification

**Suite:** `python -m pytest -q` → **184 passed**. No test touches the network
or needs an API key (scripted fake provider + fake tools throughout).

**Default-off guarantee:** with the flag unset, `agent_tools_enabled` is False
and the loop clause is skipped — the existing `agent_runner.run` branch handles
agents exactly as before.

**Registry:** with RAG on and a web provider present, the enabled tools are
`fetch_url`, `knowledge_search`, `web_search`. `create_artifact` appears only
when a skill engine is configured. The `ALLOW_SHELL/EMAIL/FILE_DELETE` flags are
all False, so no such tool is ever constructed.

**1. Low-risk tool, no gate.** Asked the `researcher` agent for the auto-sync
codename. The model chose `knowledge_search` on its own with the query
"internal codename auto-sync feature", read the passage, and answered
**Nightingale**. `citations: ['violet-notes.md']`, `tool_requests: []`,
`agent_run_id: None`.

**2. Medium-risk tool pauses.** Asked it to fetch https://example.com. Response:
`"I need your approval before continuing."` with `agent_run_id` set and
`tool_requests: [{tool: fetch_url, arguments: {url: ...}, risk: medium}]`.
The tool was **not executed** — the run stopped at the gate.

**3. Resume across HTTP requests.** `POST /api/agent-runs/{id}/resume`
`{approved: true}` rehydrated the persisted messages, executed the fetch, and
returned `status: completed` with a summary of the page and
`citations: ['https://example.com']`. The run row moved to
`completed / iterations 2 / pending 0`.

**4. Audit trail** (`tool_audit_logs`, previously unused):

| tool | risk | approved | summary |
|---|---|---|---|
| knowledge_search | low | 1 | `[violet-notes.md] # Violet Project Notes…` |
| fetch_url | medium | **0** | `awaiting approval` |
| fetch_url | medium | **1** | `Example Domain…` |

Both the blocked attempt and the approved execution are recorded, satisfying
SECURITY_RULES #6.

## Status
done

## Next
Optional follow-ups: fix the module-level `app = create_app()` side effect noted
in `agent-run-persistence_2026-07-26_log.md`; add High/Critical tools (shell,
email) now that the gate is proven; stream the trace as it happens.
