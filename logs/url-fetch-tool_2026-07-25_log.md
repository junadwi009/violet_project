# URL fetch/crawl tool with SSRF guard

- **Date:** 2026-07-25
- **Track:** 1 Chat (cross-cutting)
- **Branch:** feat/slash-canvas-settings-websearch
- **Author:** Claude (executing 2026-07-25 plan, Task 3)

## What
Added `POST /api/fetch {url}` → `{url, title, text, chars, truncated}`, backed by
`violet_assistant.web.fetch` (stdlib `urllib` + `html.parser`). Blocks
loopback/private/link-local/reserved hosts (SSRF guard) and non-http(s) schemes;
caps body size.

## Why
Feature 4 "crawling": read an exact page's readable text (complements OpenRouter
`:online` search). Kept dependency-free to match the existing stdlib-only
provider.

## Files touched
- `services/assistant-core/src/violet_assistant/web/fetch.py` (new)
- `services/assistant-core/src/violet_assistant/routes/fetch.py` (new)
- `services/assistant-core/src/violet_assistant/main.py` (include router)
- `services/assistant-core/tests/test_web_fetch.py` (new)

## Interfaces / contracts changed
- New route `POST /api/fetch`.
- New: `extract_text(html) -> (title, text)`, `is_blocked_host(host) -> bool`,
  `fetch_url(url, max_bytes=2_000_000) -> FetchResult`.

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_web_fetch.py -q` → 10 passed.

## Next
Frontend: Task 4 (api.ts additions + slash palette + web toggle).
