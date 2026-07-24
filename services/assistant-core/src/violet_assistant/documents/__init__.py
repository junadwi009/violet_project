"""Deterministic document rendering (Phase 3d).

The LLM emits a structured JSON spec (never code); the backend renders a real .docx / .pptx with
python-docx / python-pptx. Safe (no code execution) and reliable.
"""
