# Tool contract + flag-gated registry + safety settings

- **Date:** 2026-07-26
- **Track:** cross-cutting (agent tool loop, Task 1)
- **Branch:** feat/agent-tool-loop
- **Author:** Claude

## What
`tools/base.py`: `RISK_ORDER`, `ToolResult`, the `Tool` protocol, and
`wrap_untrusted()` carrying the verbatim preamble from
`docs/03_SECURITY_RULES.md`. `tools/registry.py`: `ToolRegistry` (get / enabled /
OpenAI-shaped `specs()`), `requires_confirmation()` (server-side risk gate) and
`flags_satisfied()`. Wired the four `ALLOW_*` safety flags into `Settings` for
the first time — they had lived only in `.env.example` and CLAUDE.md.

## Why
Foundation for the agent tool loop. The registry is the security boundary: a
tool that fails its flag check is never constructed, so it never reaches
`specs()` and the model cannot request what it cannot see.

## Files touched
- `services/assistant-core/src/violet_assistant/tools/base.py` (new)
- `services/assistant-core/src/violet_assistant/tools/registry.py` (new)
- `services/assistant-core/src/violet_assistant/config.py` (9 new fields)
- `services/assistant-core/tests/test_tool_registry.py` (new)

## Interfaces / contracts changed
- New: `Tool` protocol, `ToolResult`, `wrap_untrusted`, `ToolRegistry`,
  `requires_confirmation`, `flags_satisfied`.
- New env: `AGENT_TOOLS_ENABLED` (default false), `TOOL_CONFIRM_THRESHOLD`
  (high), `REQUIRE_CONFIRMATION_FOR_RISKY_TOOLS` (true), `ALLOW_SHELL_TOOLS` /
  `ALLOW_EMAIL_TOOLS` / `ALLOW_FILE_DELETE` (false), `MAX_TOOL_ITERATIONS` (5),
  `TOOL_TIMEOUT_SECONDS` (120), `MAX_TOOL_RESULT_CHARS` (8000).

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_tool_registry.py -q` → 11
passed, including an 8-case threshold x risk matrix and the global kill switch.

## Next
Task 2: the four builtin tools.
