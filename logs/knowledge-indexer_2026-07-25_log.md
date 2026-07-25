# Knowledge indexer + un-clipped extraction

- **Date:** 2026-07-25
- **Track:** 2 RAG
- **Branch:** feat/knowledge-base-and-ui-modes
- **Author:** Claude (executing knowledge-base plan, Task 4)

## What
`KnowledgeIndexer.reindex(full=False)` scans `knowledge_dir`, extracts (reusing
`extract_text` with `max_chars=None`), chunks, embeds, and upserts each file;
skips unchanged files by SHA-256; removes docs whose files vanished; captures
per-file errors without stopping the scan. Added a `max_chars` param to
`extract_text` (default keeps the 20k upload clip).

## Why
The ingestion pipeline that turns a local folder into vectors (RAG steps 0–4).

## Files touched
- `services/assistant-core/src/violet_assistant/knowledge/**` (new)
- `services/assistant-core/src/violet_assistant/ingestion/extractors.py` (SHARED SEAM: `max_chars`)
- `services/assistant-core/tests/test_indexer.py` (new)
- `services/assistant-core/tests/test_ingestion.py` (max_chars test)

## Interfaces / contracts changed
- `extract_text(filename, data, max_chars=MAX_TEXT_CHARS)` — added param, default
  preserves prior behaviour.
- New: `KnowledgeIndexer(embedder, store, knowledge_dir, chunk_size, chunk_overlap)`
  with `async reindex(full) -> {indexed, skipped, removed, chunks, errors}`.

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_indexer.py tests/test_ingestion.py -q` → 13 passed.

## Next
Task 5: vector retriever + factory wiring.
