"""Retrieval-augmented generation seam.

Track 2 (RAG) owns everything in this package. The orchestrator depends only on the
``Retriever`` protocol and the ``Chunk`` shape defined in ``base.py`` — the default wiring
uses ``NoOpRetriever`` so the assistant behaves identically until a real retriever is set
via ``RAG_PROVIDER``.
"""
