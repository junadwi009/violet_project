# SQLite vector store with cosine query

- **Date:** 2026-07-25
- **Track:** 3 Vector
- **Branch:** feat/knowledge-base-and-ui-modes
- **Author:** Claude (executing knowledge-base plan, Task 3)

## What
`SqliteVectorStore` in a dedicated `data/knowledge.db`: `knowledge_docs` +
`knowledge_chunks` tables, embeddings stored as `array('f')` BLOBs, pure-Python
cosine `query` filtered to matching model+dim, plus upsert/delete/list/stats.

## Why
Vector persistence + nearest-neighbour search for RAG, dependency-free and
isolated from the chat DB.

## Files touched
- `services/assistant-core/src/violet_assistant/vector/store/**` (new)
- `services/assistant-core/tests/test_vector_store.py` (new)

## Interfaces / contracts changed
- New: `VectorStore` protocol + `SqliteVectorStore`
  (`upsert_doc/query/delete_doc/list_docs/stats/doc_by_path`).

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_vector_store.py -q` → 3 passed.

## Next
Task 4: knowledge indexer + un-clipped extraction.
