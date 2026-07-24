from __future__ import annotations

import re

from pydantic import BaseModel, Field


class Skill(BaseModel):
    id: str
    name: str
    description: str = ""
    kind: str  # "chartjs" | "html"
    triggers: list[str] = Field(default_factory=list)
    prompt: str

    def match_score(self, text: str) -> int:
        """Length of the longest trigger that matches ``text`` on word boundaries (0 if none).

        Longer matches are more specific, so a skill triggered by "interactive chart" beats one
        triggered by "chart" when both appear.
        """
        best = 0
        for trigger in self.triggers:
            pattern = r"(?<!\w)" + re.escape(trigger.lower()) + r"(?!\w)"
            if re.search(pattern, text.lower()):
                best = max(best, len(trigger))
        return best

    def matches(self, text: str) -> bool:
        return self.match_score(text) > 0
