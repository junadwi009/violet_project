# 06 — Parallel Development Map (Audit + Workstream Mapping)

> Audited 2026-07-24 against branch `codex/phase-1-text-mvp`.
> Purpose: let 6 workstreams progress **in parallel** without stepping on each other.
> Read this before starting any of the 6 tracks. Every change must be logged per the rule in
> [`../CLAUDE.md`](../CLAUDE.md) → *Update Log Rule*.

---

## 1. Current state (audit)

### What actually exists today

| Area | Status | Where |
|---|---|---|
| Generative chat | ✅ Working (mock + OpenAI-compatible) | `services/assistant-core/src/violet_assistant/{llm,orchestrator,routes}` |
| Personality | ✅ Working (2 JSON profiles) | `configs/personality/`, `personality/loader.py` |
| Memory (approval-gated) | ✅ Working, regex extractor | `memory/extractor.py`, `persistence/sqlite_store.py` |
| RAG | ❌ Does not exist | — |
| Vector / embeddings | ❌ Does not exist (`VECTOR_PROVIDER=none` stub only) | `.env.example:33` |
| 3D avatar | 🟡 CSS placeholder only | `apps/web-client/src/components/AvatarPanel.tsx` |
| Voice recognition (STT) | 🟡 Two disconnected halves (see below) | `services/speech-service`, `apps/web-client/src/lib/speech.ts` |
| Voice clone (TTS) | 🟡 Two disconnected halves (see below) | `services/tts-service`, `apps/web-client/src/lib/speech.ts` |

### Critical wiring gaps (important for planning)

1. **`assistant-core` does not call `speech-service` or `tts-service`.** They are three independent
   FastAPI apps. `main.py` in assistant-core only mounts chat/memory/personality/health.
2. **The web client bypasses both voice services.** `lib/speech.ts` uses the browser Web Speech API
   (`webkitSpeechRecognition` + `speechSynthesis`) directly. The mock STT/TTS services are unused.
3. **The mock STT "transcribes" text, not audio** (`mock_stt.py` takes a `text` field). Real STT needs
   an audio-bytes contract change.
4. **Mock TTS returns `audio_base64=None`.** Real TTS/voice-clone must actually populate audio.
5. **The orchestrator has no retrieval step.** `chat_orchestrator.py` builds `[system_prompt, *history]`
   — there is no seam where RAG context can be injected yet. **This is the one shared hot file** the RAG
   track must touch. See §4 for the recommended no-op hook that keeps that change tiny.

### Stack baseline

- Backend: Python ≥3.11, FastAPI, Pydantic 2, stdlib `urllib` for LLM HTTP (no httpx yet). SQLite via `sqlite3`.
- Provider pattern everywhere: a `Protocol` interface + a `mock` impl + a factory. **Reuse this pattern for every new track.**
- Frontend: React 19 + Vite + TypeScript. Only dep beyond React is `lucide-react`. No three.js, no audio libs.
- Tests: `pytest`, per-service `tests/` dirs already wired in `pyproject.toml`.

---

## 2. The provider/interface pattern (the rule that makes parallel work safe)

Every track plugs a real implementation behind an existing (or new) `Protocol`, selected by a factory
reading an env var. **Never edit a `mock_*` file to add real behavior — add a sibling provider and switch
via env.** This is what keeps tracks from colliding and keeps `LLM_PROVIDER=mock` (no-key) working.

Existing contracts you build against:

- `llm/base.py` → `LLMProvider.chat(messages, options) -> LLMResponse` (+ `health`)
- `speech-service/providers/base.py` → `STTProvider.transcribe(...) -> Transcript`
- `tts-service/providers/base.py` → `TTSProvider.synthesize(...) -> AudioResult`

---

## 3. Workstream mapping (ownership boundaries)

Boundaries are drawn so each track owns a **disjoint set of files**. Where a track must touch a shared
file, it is called out explicitly with the minimal-diff approach.

### Track 1 — Generative chat
- **Owns:** `assistant-core/src/violet_assistant/llm/*`, `orchestrator/chat_orchestrator.py`, `routes/chat.py`, `schemas/chat.py`
- **Do next:** streaming responses (SSE endpoint + `stream=True` in `openai_compatible_provider.py`), real emotion tagging, an Anthropic provider (`claude-*` — see the `claude-api` skill for model ids), swap `urllib` → `httpx`.
- **Interface to hold stable:** `LLMProvider`. Add methods as optional; don't break `chat()`.
- **Collision risk:** LOW. Only RAG (Track 2) also reads the orchestrator — see §4.

### Track 2 — RAG
- **Owns (new):** `assistant-core/src/violet_assistant/rag/` (new package: `retriever.py`, `base.py`, `mock_retriever.py`, `factory.py`)
- **Depends on:** Track 3 (vector store). Develop against the `Retriever` interface with a mock/no-op so you are **not blocked** by Track 3.
- **Do next:** define `Retriever.retrieve(query, k) -> list[Chunk]`; ingest pipeline (chunk → embed → upsert); inject retrieved context into the system prompt.
- **Shared file:** `chat_orchestrator.py` (one injection point — see §4).
- **Collision risk:** MEDIUM (orchestrator). Mitigated by the §4 hook.

### Track 3 — Vectorizing layer (for RAG)
- **Owns (new):** `assistant-core/src/violet_assistant/vector/` (new package: `embeddings/base.py` + `mock`/real, `store/base.py` + `mock`/real, `factory.py`), driven by `VECTOR_PROVIDER` env.
- **Do next:** `EmbeddingProvider.embed(texts) -> list[vector]` (local: sentence-transformers / Ollama `/embeddings`); `VectorStore.upsert/query` (local dev: sqlite-vec or chroma/faiss; prod: pgvector per Phase 5 roadmap).
- **Interface consumers:** only Track 2. Agree the `Chunk`/vector shape with Track 2 **on day 1**, then both build independently.
- **Collision risk:** LOW (new package, new env var).

### Track 4 — 3D model displaying
- **Owns:** `apps/web-client/` avatar surface only — `components/AvatarPanel.tsx`, `lib/avatar.ts`, a new `components/VrmAvatar.tsx`, `public/avatar/violet.vrm` (asset already present locally, git-ignored — do not commit licensed VRM).
- **Do next:** add `three` + `@pixiv/three-vrm`; render the VRM; map the existing `AvatarState`/`AvatarEmotion` unions to expressions; idle/blink loop.
- **Interface to hold stable:** keep consuming the `AvatarState`/`AvatarEmotion` props `AvatarPanel` already receives — do not change `App.tsx`'s state machine. Lip-sync consumes Track 6's audio (viseme/amplitude) — agree that signal with Track 6, default to none.
- **Collision risk:** LOW. Frontend-isolated; touches no backend.

### Track 5 — Voice recognition (STT)
- **Owns:** `services/speech-service/*`. Add `providers/faster_whisper_stt.py` (or `whisper_cpp_stt.py`) + a factory reading `STT_PROVIDER`.
- **Contract change needed:** `transcribe` must accept **audio bytes**, not text. Update `schemas.py` (`TranscribeRequest`) and the mock together so tests stay green.
- **Wiring task (owned here):** decide STT path — either the web client posts audio to `speech-service`, or keep browser Web Speech for now and make `speech-service` the "real/offline" path. Document the choice in your log.
- **Collision risk:** LOW (own service). Touches `web-client/lib/speech.ts` only if you switch the client off browser STT — coordinate that one file with Track 4/6.

### Track 6 — Voice clone (TTS)
- **Owns:** `services/tts-service/*`. Add `providers/xtts_tts.py` / `coqui` / `piper` + factory reading `TTS_PROVIDER`, `TTS_VOICE`. Must return real `audio_base64`.
- **Do next:** speaker-embedding / reference-clip handling for cloning; expose a viseme or amplitude track for Track 4 lip-sync (optional, agree the shape).
- **Wiring task (owned here):** web client should play returned audio instead of `speechSynthesis` when `TTS_PROVIDER != mock`. Touches `web-client/lib/speech.ts` + `App.tsx` output branch.
- **Collision risk:** LOW (own service) + the shared `speech.ts` output branch with Track 5.

---

## 4. The one shared seam: RAG hook in the orchestrator

To let Track 2 (RAG) work without editing Track 1's logic repeatedly, add a **single no-op retriever
dependency** to `ChatOrchestrator` up front:

```python
# chat_orchestrator.py — inject a Retriever (default no-op) in __init__
# then, before building `messages`:
context_chunks = await self.retriever.retrieve(request.content)   # [] for no-op
system_prompt = build_system_prompt(profile, context=context_chunks)
```

Land this tiny seam first (owned by Track 1 + Track 2 jointly, ~15 lines). After that, Track 2 iterates
entirely inside `rag/` and never reopens the orchestrator. This is the only file two tracks share.

---

## 5. Suggested branch / worktree layout

One branch per track off a shared integration base so they merge cleanly:

```
codex/phase-1-text-mvp   (current base)
 ├─ track/chat-streaming        (Track 1)
 ├─ track/rag                   (Track 2)  ── coordinates Chunk shape with track/vector
 ├─ track/vector                (Track 3)
 ├─ track/avatar-vrm            (Track 4)  ── frontend only
 ├─ track/stt-whisper           (Track 5)
 └─ track/tts-voiceclone        (Track 6)
```

Day-1 coordination (do these before fanning out):
1. Land the §4 orchestrator hook (Tracks 1+2).
2. Freeze the `Chunk`/embedding-vector shape (Tracks 2+3).
3. Freeze the lip-sync audio signal shape (Tracks 4+6), default "none".
4. Agree who owns `web-client/lib/speech.ts` edits (Tracks 5+6) — recommend Track 6 owns the output
   branch, Track 5 owns the input branch.

---

## 6. Quick reference — files per track

| Track | Primary paths |
|---|---|
| 1 Chat | `assistant-core/.../llm/`, `.../orchestrator/`, `.../routes/chat.py` |
| 2 RAG | `assistant-core/.../rag/` (new) |
| 3 Vector | `assistant-core/.../vector/` (new), `VECTOR_PROVIDER` |
| 4 Avatar | `web-client/src/components/{AvatarPanel,VrmAvatar}.tsx`, `web-client/src/lib/avatar.ts` |
| 5 STT | `services/speech-service/`, `web-client/src/lib/speech.ts` (input) |
| 6 TTS | `services/tts-service/`, `web-client/src/lib/speech.ts` (output) |
