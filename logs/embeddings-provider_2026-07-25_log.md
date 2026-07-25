# Embedding providers (mock + openai-compatible) + config

- **Date:** 2026-07-25
- **Track:** 3 Vector
- **Branch:** feat/knowledge-base-and-ui-modes
- **Author:** Claude (executing knowledge-base plan, Task 1)

## What
New `vector/embeddings/` package: `EmbeddingProvider` protocol, deterministic
offline `MockEmbedder` (256-dim, L2-normalized, default), an
`OpenAICompatibleEmbedder` (Ollama `/v1/embeddings` and compatible), and a
factory reading `EMBED_PROVIDER`. Added RAG/knowledge config fields to `Settings`.

## Why
Foundation for the local knowledge base (Feature: RAG). Mock default keeps the
pipeline runnable with zero setup, mirroring `LLM_PROVIDER=mock`.

## Files touched
- `services/assistant-core/src/violet_assistant/vector/**` (new package)
- `services/assistant-core/src/violet_assistant/config.py` (new fields)
- `services/assistant-core/tests/test_embeddings.py` (new)

## Interfaces / contracts changed
- New: `EmbeddingProvider.embed(texts) -> list[list[float]]`, `create_embedder`.
- New env: `EMBED_PROVIDER/BASE_URL/MODEL/API_KEY`, `KNOWLEDGE_DIR/DB`,
  `KNOWLEDGE_SCAN_ON_STARTUP`, `KNOWLEDGE_CHUNK_SIZE/OVERLAP`.

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_embeddings.py -q` → 3 passed.

## Next
Task 2: chunker.
