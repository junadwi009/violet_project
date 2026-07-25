# Chat: explicit-skill invocation + web-search routing

- **Date:** 2026-07-25
- **Track:** 1 Chat (cross-cutting)
- **Branch:** feat/slash-canvas-settings-websearch
- **Author:** Claude (executing 2026-07-25 plan, Task 2)

## What
`ChatOrchestrator` now accepts `preferences` (effective temperature/model per
request) and a `web_provider`. New precedence: mock → explicit agent →
web-search → explicit skill (`skill_id`) → auto-detected skill → auto agent →
cascade → provider. Added `violet_assistant.web.search` (`web_answer` /
`parse_web_response`) using OpenRouter `:online`, and `SkillRegistry.get`.

## Why
Feature 1 (explicit `/slash` skill invocation) and Feature 4 (web search).
Explicit skill bypasses keyword matching; web search reuses the OpenRouter
setup and returns cited answers.

## Files touched
- `services/assistant-core/src/violet_assistant/web/__init__.py` (new)
- `services/assistant-core/src/violet_assistant/web/search.py` (new)
- `services/assistant-core/src/violet_assistant/skills/registry.py` (`get`)
- `services/assistant-core/src/violet_assistant/schemas/chat.py` (`skill_id`, `web_search`, `citations`)
- `services/assistant-core/src/violet_assistant/orchestrator/chat_orchestrator.py` (SHARED SEAM: routing + prefs)
- `services/assistant-core/src/violet_assistant/main.py` (build web provider; pass prefs/web_provider)
- `services/assistant-core/tests/test_web_search.py` (new)
- `services/assistant-core/tests/test_skills.py` (registry.get test)
- `services/assistant-core/tests/test_chat_orchestrator.py` (routing tests)

## Interfaces / contracts changed
- `ChatRequest.skill_id: str | None`, `ChatRequest.web_search: bool`.
- `ChatResponse.citations: list[str]`.
- `ChatOrchestrator.__init__` gains optional `preferences`, `web_provider`.
- `web_answer(provider, model, messages) -> WebAnswer(text, citations)` — reaches
  into `OpenAICompatibleProvider._request_json` to read citation annotations.

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_web_search.py tests/test_skills.py tests/test_chat_orchestrator.py -q` → 16 passed.
Full suite → 85 passed.

## Next
Task 3: `/api/fetch` URL crawl tool with SSRF guard.
