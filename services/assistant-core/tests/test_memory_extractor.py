from __future__ import annotations

from violet_assistant.memory.extractor import extract_memory_candidates


def test_extracts_preference_candidate() -> None:
    candidates = extract_memory_candidates(
        "I prefer concise engineering updates.", "message-1"
    )

    assert len(candidates) == 1
    assert candidates[0].memory_type == "profile"
    assert candidates[0].content == "concise engineering updates"
    assert candidates[0].source_message_id == "message-1"


def test_cleans_explicit_remember_preference() -> None:
    candidates = extract_memory_candidates(
        "Remember that I prefer concise engineering updates.", "message-1"
    )

    assert len(candidates) == 1
    assert candidates[0].content == "concise engineering updates"


def test_skips_secret_like_content() -> None:
    candidates = extract_memory_candidates(
        "Remember that my API key is abc123.", "message-1"
    )

    assert candidates == []
