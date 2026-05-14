from __future__ import annotations

import re
from uuid import uuid4

from violet_assistant.memory.schema import MemoryCandidate


SECRET_HINTS = {"api key", "password", "secret", "token", "credential"}


def extract_memory_candidates(
    content: str, source_message_id: str
) -> list[MemoryCandidate]:
    lowered = content.lower()
    if any(secret_hint in lowered for secret_hint in SECRET_HINTS):
        return []

    patterns = [
        (
            "profile",
            r"\bremember that (?P<fact>.+)",
            "User explicitly asked Violet to remember this.",
        ),
        (
            "profile",
            r"\bmy name is (?P<fact>.+)",
            "User shared a stable profile detail.",
        ),
        (
            "negative_preference",
            r"\bi (?:do not|don't) like (?P<fact>.+)",
            "User shared a negative preference.",
        ),
        (
            "profile",
            r"\bi prefer (?P<fact>.+)",
            "User shared a preference.",
        ),
    ]

    candidates: list[MemoryCandidate] = []
    matched_spans: list[tuple[int, int]] = []
    for memory_type, pattern, reason in patterns:
        match = re.search(pattern, content, flags=re.IGNORECASE)
        if match is None:
            continue
        if any(
            match.start() < end and start < match.end()
            for start, end in matched_spans
        ):
            continue
        fact = match.group("fact").strip().rstrip(".")
        if not fact:
            continue
        matched_spans.append((match.start(), match.end()))
        candidates.append(
            MemoryCandidate(
                id=str(uuid4()),
                memory_type=memory_type,
                content=fact,
                reason=reason,
                source_message_id=source_message_id,
                confidence=0.65,
            )
        )

    return candidates
