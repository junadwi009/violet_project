# RAG Retriever Seam in Orchestrator

- **Date:** 2026-07-24
- **Track:** cross-cutting (unblocks Track 2 RAG + Track 3 Vector)
- **Branch:** codex/phase-1-text-mvp
- **Author:** Claude Code

## What
Added a no-op `Retriever` seam so the chat orchestrator retrieves context before building the
system prompt. Default behavior is unchanged (empty retrieval); Track 2 now plugs a real
retriever behind the `Retriever` protocol without reopening the orchestrator.

## Why
`chat_orchestrator.py` is the one file RAG must touch (per `docs/06_PARALLEL_DEV_MAP.md` §4).
Landing the seam once, up front, lets Tracks 2 and 3 develop entirely in their own packages.

## Files touched
- `services/assistant-core/src/violet_assistant/rag/__init__.py` — new package
- `services/assistant-core/src/violet_assistant/rag/base.py` — new: `Chunk` dataclass + `Retriever` protocol (the frozen Track 2/3 contract)
- `services/assistant-core/src/violet_assistant/rag/no_op_retriever.py` — new: default, returns `[]`
- `services/assistant-core/src/violet_assistant/rag/factory.py` — new: `create_retriever` from `RAG_PROVIDER`
- `services/assistant-core/src/violet_assistant/orchestrator/chat_orchestrator.py` — **shared seam**: inject `retriever` (default no-op), retrieve before prompt build
- `services/assistant-core/src/violet_assistant/personality/loader.py` — `build_system_prompt` gained optional `context` param (appends a "Retrieved context" block)
- `services/assistant-core/src/violet_assistant/config.py` — added `rag_provider` (env `RAG_PROVIDER`, default `none`)
- `services/assistant-core/src/violet_assistant/main.py` — wire `create_retriever` into the orchestrator
- `.env.example` — added `RAG_PROVIDER=none`
- `services/assistant-core/tests/test_retriever_seam.py` — new: 4 tests (factory default, no-op clean prompt, injection, backward-compat default)
- `services/assistant-core/tests/test_chat_orchestrator.py` — added `rag_provider="none"` to the manual `Settings` build

## Interfaces / contracts changed
- **New (frozen) contract:** `rag.base.Chunk(text, source, score, metadata)` and
  `Retriever.retrieve(query, k) -> list[Chunk]`. Track 2 + Track 3 depend on this — change only via a coordinated log entry.
- `build_system_prompt(profile, context=None)` — additive, backward-compatible.
- `Settings` gained `rag_provider`. Any manual `Settings(...)` construction must now pass it.
- New env var `RAG_PROVIDER` (default `none`).

## Status
done. No behavioral change with default `RAG_PROVIDER=none`.

## Verification
- `python -m pytest -q` → **20 passed** (was 16 before; +4 new seam tests, existing suite green).
- Wiring smoke: `load_settings()` → `create_retriever()` → retriever `name = none` (empty retrieval).
- Note: `main.create_app()` needs `fastapi` installed (not present in the audit interpreter); the
  fastapi-independent wiring path is verified above and by the orchestrator tests.

## Next
- **Track 3 (Vector):** implement `EmbeddingProvider` + `VectorStore` under a new `vector/` package,
  driven by `VECTOR_PROVIDER`. Agree nothing new with Track 2 beyond the `Chunk` shape.
- **Track 2 (RAG):** add a `vector` retriever in `rag/` that embeds the query (Track 3) and maps
  hits → `Chunk`, then set `RAG_PROVIDER=vector`. No orchestrator changes required.
