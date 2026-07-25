# Fix: gitignore knowledge/, drop citations on skill answers, repair startup scan

- **Date:** 2026-07-26
- **Track:** 2 RAG / cross-cutting
- **Branch:** fix/knowledge-gitignore-and-skill-citations
- **Author:** Claude (found by running the app locally)

## What
Three fixes, two requested and one found by actually running the app:

1. **`/knowledge/` added to `.gitignore`.** The knowledge folder holds personal /
   internal source documents; it was untracked-but-committable, so `git add -A`
   would have published them. Mirrors the existing `/memory/` rule.
2. **Skill answers no longer carry retrieved citations.** `SkillEngine.generate`
   only ever receives `skill.prompt` + `request.content` — never the retrieved
   context — so citing the knowledge base on a chart/deck answer was misleading.
   Both skill branches (explicit `skill_id` and auto-detected) now clear
   `citations`. Non-skill paths (agent / cascade / provider) still cite, since
   they do receive the context in the system prompt.
3. **Startup knowledge scan actually runs now.** `create_app()` is sync and did
   `asyncio.new_event_loop().run_until_complete(indexer.reindex())`. Under
   uvicorn a loop is already running in that thread, so this raised, was
   swallowed by a bare `except`, and left `RuntimeWarning: coroutine
   'KnowledgeIndexer.reindex' was never awaited` — i.e. `KNOWLEDGE_SCAN_ON_STARTUP`
   silently never worked. The scan moved into the FastAPI `startup` event where
   it is properly awaited.

## Why
(1) privacy, (2) misleading attribution, (3) a documented-but-broken feature —
the risk was flagged in the Phase A plan and it did in fact bite under uvicorn.

## Files touched
- `.gitignore`
- `services/assistant-core/src/violet_assistant/orchestrator/chat_orchestrator.py` (SHARED SEAM)
- `services/assistant-core/src/violet_assistant/main.py` (SHARED SEAM: startup lifecycle)
- `services/assistant-core/tests/test_chat_orchestrator.py` (3 citation tests)
- `services/assistant-core/tests/test_knowledge_routes.py` (startup-scan regression test)

## Interfaces / contracts changed
- none (behavioral fixes only)

## Status
done

## Verification
- `python -m pytest -q` → **142 passed**.
- The startup-scan regression test is **async on purpose** (reproduces uvicorn's
  already-running-loop condition). Verified it genuinely catches the bug:
  passes with the fix, FAILS when the buggy code is restored. A sync version of
  the same test passed against the bug and was therefore worthless.
- Live: fresh `knowledge.db` + `KNOWLEDGE_AUTO_SYNC=false` → server boots with
  **0** "never awaited" warnings and `/api/knowledge` reports
  `docs: 1, chunks: 1` with `last_sync: {local: None}`, proving the *startup
  scan* (not the auto-sync loop) did the indexing.
- Live: normal question keeps its `violet-notes.md` citation; `skill_id=chart`
  returns an artifact with `citations: []`.

## Next
Optional follow-ups: `/run-skill-generator` to capture the local run recipe
(venv install + env vars + launch.json); suppress citations for the mock
provider path too if it ever matters.
