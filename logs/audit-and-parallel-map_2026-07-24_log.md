# Audit + Parallel Development Map

- **Date:** 2026-07-24
- **Track:** cross-cutting (setup for Tracks 1–6)
- **Branch:** codex/phase-1-text-mvp
- **Author:** Claude Code (audit session)

## What
Audited the `project_violet` repo, mapped the 6 planned workstreams (Generative chat, RAG,
Vectorizing layer, 3D model display, Voice recognition, Voice clone) to concrete files and
ownership boundaries, and established the update-log rule.

## Why
Enable 6 tracks to be developed in parallel without file collisions, and start a durable
change-log discipline so parallel work stays traceable.

## Files touched
- `docs/06_PARALLEL_DEV_MAP.md` — new: audit + workstream mapping + collision analysis
- `CLAUDE.md` — new "Update Log Rule" section + pointer to the map
- `logs/_TEMPLATE.md` — new log template
- `logs/audit-and-parallel-map_2026-07-24_log.md` — this file

## Interfaces / contracts changed
None. Documentation + convention only. Existing `Protocol` interfaces
(`LLMProvider`, `STTProvider`, `TTSProvider`) documented as the extension points.

## Key findings
1. Chat pipeline works (mock + OpenAI-compatible). RAG and vector layer do **not exist yet**.
2. `assistant-core` does not call `speech-service`/`tts-service`; web client uses browser Web
   Speech API, so both mock voice services are currently unwired.
3. Mock STT takes text (not audio); mock TTS returns no audio — both need contract changes for real impls.
4. `chat_orchestrator.py` has no retrieval seam — it is the one file RAG must touch. A no-op
   `Retriever` hook is proposed (map §4) to keep that shared change minimal.
5. Avatar is a CSS placeholder; frontend has no three.js.

## Status
done (audit + mapping + rule). No code behavior changed.

## Verification
Read-only audit; no code modified, so no test run required. Repo builds/tests unchanged.

## Next
- Day-1 coordination items in `docs/06_PARALLEL_DEV_MAP.md` §5 (land orchestrator RAG hook,
  freeze Chunk/vector shape, freeze lip-sync signal, assign `speech.ts` ownership).
- Then fan out one branch per track.
