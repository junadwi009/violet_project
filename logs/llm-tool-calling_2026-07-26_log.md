# Native function-calling in the LLM layer

- **Date:** 2026-07-26
- **Track:** 1 Chat (agent tool loop, Task 3)
- **Branch:** feat/agent-tool-loop
- **Author:** Claude

## What
Added `ToolCall` and extended the frozen dataclasses: `Message.tool_call_id` /
`Message.tool_calls` (for the OpenAI round-trip), `LLMOptions.tools`,
`LLMResponse.tool_calls`. `OpenAICompatibleProvider` now serialises tool/assistant
messages, sends `tools` when present, and parses `tool_calls` (malformed
`arguments` JSON degrades to `{}` and is surfaced to the model as a tool error
rather than raising).

## Why
Native function-calling is the mechanism for the agent tool loop — far more
reliable than parsing prose out of the response.

## Files touched
- `services/assistant-core/src/violet_assistant/llm/base.py` (SHARED SEAM)
- `services/assistant-core/src/violet_assistant/llm/openai_compatible_provider.py`
- `services/assistant-core/tests/test_provider_tools.py` (new)

## Interfaces / contracts changed
- All additive with defaults: every existing call site is untouched, which the
  full suite confirms. The mock provider is never given tools, so
  `LLM_PROVIDER=mock` still runs with zero config.

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_provider_tools.py -q` → 4 passed.
Full suite → **167 passed** (was 146 before this branch; no regressions).

## Next
Task 4: the agent loop.
