# Vector retriever + RAG_PROVIDER=vector wiring

- **Date:** 2026-07-25
- **Track:** 2 RAG
- **Branch:** feat/knowledge-base-and-ui-modes
- **Author:** Claude (executing knowledge-base plan, Task 5)

## What
`VectorRetriever` implements the existing `Retriever` protocol (embed query →
store cosine query → `Chunk`s with source + score). `create_retriever` now
supports `RAG_PROVIDER=vector`, building the embedder + SQLite store; unknown
providers still fail loudly.

## Why
Connects the knowledge base to the orchestrator's existing retrieval seam.

## Files touched
- `services/assistant-core/src/violet_assistant/rag/vector_retriever.py` (new)
- `services/assistant-core/src/violet_assistant/rag/factory.py` (vector branch)
- `services/assistant-core/tests/test_vector_retriever.py` (new)

## Interfaces / contracts changed
- New: `VectorRetriever(embedder, store, model)`.
- `RAG_PROVIDER=vector` now supported. Retriever `model` = embedder `name`
  (matches what the indexer stores).

## Status
done

## Verification
`python -m pytest tests/test_vector_retriever.py tests/test_retriever_seam.py -q` → 5 passed.

## Next
Task 6: knowledge routes + main wiring + retrieved-source citations.
