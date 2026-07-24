"""Pluggable store for *approved* memories.

Candidates (the pre-approval inbox) stay in SQLite. Approved memories go through an
``ApprovedMemoryStore`` backend selected by ``MEMORY_BACKEND``:
- ``files``  — markdown files in a directory (default; local / VPS / Drive-synced)
- ``sqlite`` — the original memories table
A future ``gdrive`` backend implements the same interface.
"""
