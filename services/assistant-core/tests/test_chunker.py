from __future__ import annotations

from violet_assistant.vector.chunker import chunk_text


def test_short_text_is_one_chunk():
    assert chunk_text("hello world") == ["hello world"]


def test_empty_text_is_no_chunks():
    assert chunk_text("   ") == []


def test_long_text_splits_with_overlap():
    para = ("word " * 400).strip()  # ~2000 chars
    chunks = chunk_text(para, size=500, overlap=100)
    assert len(chunks) >= 4
    assert all(len(c) <= 700 for c in chunks)  # size + overlap slack


def test_paragraph_boundaries_preferred():
    text = "Alpha para.\n\nBeta para.\n\nGamma para."
    chunks = chunk_text(text, size=12, overlap=0)
    assert "Alpha para." in chunks[0]
