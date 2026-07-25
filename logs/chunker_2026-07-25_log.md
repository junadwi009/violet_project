# Paragraph-aware text chunker

- **Date:** 2026-07-25
- **Track:** 3 Vector
- **Branch:** feat/knowledge-base-and-ui-modes
- **Author:** Claude (executing knowledge-base plan, Task 2)

## What
`vector/chunker.py`: pure `chunk_text(text, size=1000, overlap=150)` that packs
paragraphs to ~size chars with char overlap and hard-splits oversized paragraphs.

## Why
Documents must be split into passages before embedding (RAG step 2).

## Files touched
- `services/assistant-core/src/violet_assistant/vector/chunker.py` (new)
- `services/assistant-core/tests/test_chunker.py` (new)

## Interfaces / contracts changed
- New: `chunk_text(text, size, overlap) -> list[str]`.

## Status
done

## Verification
`python -m pytest services/assistant-core/tests/test_chunker.py -q` → 4 passed.

## Next
Task 3: SQLite vector store.
