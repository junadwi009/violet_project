# Tool trace + approval card in chat

- **Date:** 2026-07-26
- **Track:** 1 Chat (web-client, agent tool loop, Task 7)
- **Branch:** feat/agent-tool-loop
- **Author:** Claude

## What
`ToolTrace` renders a collapsed line under an answer (`2 tool steps ·
knowledge_search · fetch_url`) that expands to show arguments and result
summaries. `ToolApproval` renders an amber card with the tool name, pretty-printed
arguments, a risk badge and Approve / Reject, calling
`POST /api/agent-runs/{id}/resume`. `App` stores the new response fields, clears
the card on the originating message after a decision, and appends the continued
answer.

## Why
The agent's actions must be auditable from the UI, and a paused run needs a way to
be approved or rejected (SECURITY_RULES #5).

## Files touched
- `apps/web-client/src/lib/api.ts` (`ToolTraceEntry`, `ToolRequest`, `ResumeResult`, `resumeAgentRun`)
- `apps/web-client/src/components/ToolTrace.tsx` (new)
- `apps/web-client/src/components/ToolApproval.tsx` (new)
- `apps/web-client/src/components/ChatTimeline.tsx` (SHARED SEAM)
- `apps/web-client/src/App.tsx` (SHARED SEAM: decision handler)

## Interfaces / contracts changed
- `ChatResponse.tool_requests` retyped from the placeholder `unknown[]` to
  `ToolRequest[]` — it had been declared but never populated since the original
  blueprint, so nothing depended on the old type.
- `ChatTimeline` props: `onToolDecision`, `decisionBusy`.

## Status
done

## Verification
`npm run build` → clean. Two type errors were caught and fixed during the build:
a duplicate `tool_requests` declaration on `ChatResponse` and the resulting
`SetStateAction` mismatch in `App`.

## Next
Final end-to-end verification with the loop enabled.
