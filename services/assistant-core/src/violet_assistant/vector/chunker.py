from __future__ import annotations

import re


def chunk_text(text: str, size: int = 1000, overlap: int = 150) -> list[str]:
    """Split text into ~size-char chunks on paragraph boundaries, with char overlap."""
    text = text.strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > size:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = (tail + "\n\n" + para).strip()
        else:
            current = (current + "\n\n" + para).strip() if current else para
        # a single oversized paragraph: hard-split it
        while len(current) > size:
            chunks.append(current[:size])
            current = (current[size - overlap :] if overlap else current[size:]).strip()
    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]
