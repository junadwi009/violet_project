from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class PersonalityProfile(BaseModel):
    id: str
    name: str
    language: str = "id"
    tone: str = "calm, strategic, loyal, direct"
    verbosity: str = "medium"
    style_rules: list[str] = Field(default_factory=list)
    safety_rules: list[str] = Field(default_factory=list)


class PersonalityLoader:
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir

    def load(self, profile_id: str) -> PersonalityProfile:
        profile_path = self.config_dir / f"{profile_id}.json"
        if not profile_path.exists():
            raise FileNotFoundError(f"Personality profile not found: {profile_id}")

        raw_profile = json.loads(profile_path.read_text(encoding="utf-8"))
        return PersonalityProfile.model_validate(raw_profile)

    def list_profiles(self) -> list[PersonalityProfile]:
        if not self.config_dir.exists():
            return []
        return [
            PersonalityProfile.model_validate(
                json.loads(path.read_text(encoding="utf-8"))
            )
            for path in sorted(self.config_dir.glob("*.json"))
        ]


def build_system_prompt(profile: PersonalityProfile) -> str:
    style_rules = "\n".join(f"- {rule}" for rule in profile.style_rules)
    safety_rules = "\n".join(f"- {rule}" for rule in profile.safety_rules)
    return (
        f"You are {profile.name}, a local-first personal assistant.\n"
        f"Language: {profile.language}\n"
        f"Tone: {profile.tone}\n"
        f"Verbosity: {profile.verbosity}\n\n"
        f"Style rules:\n{style_rules or '- Use clear, helpful answers.'}\n\n"
        f"Safety rules:\n{safety_rules or '- Ask before risky actions.'}"
    )

