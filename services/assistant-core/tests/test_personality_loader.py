from __future__ import annotations

import json

import pytest

from violet_assistant.personality.loader import (
    PersonalityLoader,
    build_system_prompt,
)


def test_personality_loader_reads_profile(tmp_path) -> None:
    profile = {
        "id": "violet.default",
        "name": "Violet",
        "language": "id",
        "tone": "calm",
        "verbosity": "medium",
        "style_rules": ["Separate facts from assumptions."],
        "safety_rules": ["Ask before risky actions."],
    }
    (tmp_path / "violet.default.json").write_text(
        json.dumps(profile), encoding="utf-8"
    )

    loaded = PersonalityLoader(tmp_path).load("violet.default")
    prompt = build_system_prompt(loaded)

    assert loaded.name == "Violet"
    assert "Separate facts from assumptions." in prompt
    assert "Ask before risky actions." in prompt


def test_personality_loader_raises_for_missing_profile(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        PersonalityLoader(tmp_path).load("missing")

