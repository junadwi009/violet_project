# Four builtin tools (knowledge, artifact, web search, fetch)

- **Date:** 2026-07-26
- **Track:** cross-cutting (agent tool loop, Task 2)
- **Branch:** feat/agent-tool-loop
- **Author:** Claude

## What
`KnowledgeSearchTool` (low, local, returns passages + source citations),
`CreateArtifactTool` (low, invokes a skill so an agent can answer *with* a chart),
`WebSearchTool` and `FetchUrlTool` (medium, both `untrusted=True`).
`create_tool_registry()` constructs only the tools whose dependencies exist and
whose `ALLOW_*` flags pass.

## Why
The capability set for the agent loop. `fetch_url` reuses the existing
SSRF-guarded `web.fetch.fetch_url` unchanged; `web_search` reuses `web_answer`.

## Files touched
- `services/assistant-core/src/violet_assistant/tools/builtin/**` (new)
- `services/assistant-core/src/violet_assistant/tools/registry.py` (factory)
- `services/assistant-core/tests/test_builtin_tools.py` (new)

## Interfaces / contracts changed
- New: `KnowledgeSearchTool`, `CreateArtifactTool`, `WebSearchTool`,
  `FetchUrlTool`, `create_tool_registry(...)`.

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_builtin_tools.py -q` → 6
passed. Includes: SSRF block still enforced through the tool wrapper, unknown
skill rejected, and the factory omitting tools whose deps are absent.

## Next
Task 3: native function-calling in the LLM layer.
