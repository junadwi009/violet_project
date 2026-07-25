from __future__ import annotations

import json
from pathlib import Path

from violet_assistant.skills.schema import Skill


class SkillRegistry:
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir

    def list_skills(self) -> list[Skill]:
        if not self.config_dir.exists():
            return []
        skills: list[Skill] = []
        for path in sorted(self.config_dir.glob("*.json")):
            try:
                skills.append(Skill.model_validate(json.loads(path.read_text(encoding="utf-8"))))
            except (ValueError, KeyError):
                continue  # skip malformed skill files
        return skills

    def get(self, skill_id: str) -> Skill | None:
        """Return the skill with this exact id, or None. Used for explicit /slash invocation."""
        for skill in self.list_skills():
            if skill.id == skill_id:
                return skill
        return None

    def detect(self, text: str) -> Skill | None:
        """Return the best-matching skill (most specific / longest trigger). None if no match.

        Rule-based and zero-cost. Ties break by filename order (stable via list_skills sort).
        """
        best: Skill | None = None
        best_key = (0, 0)  # (priority, trigger length)
        for skill in self.list_skills():
            score = skill.match_score(text)
            if score == 0:
                continue
            key = (skill.priority, score)
            if key > best_key:
                best_key = key
                best = skill
        return best
