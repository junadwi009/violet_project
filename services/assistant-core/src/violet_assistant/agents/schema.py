from __future__ import annotations

import re

from pydantic import BaseModel, Field


class Agent(BaseModel):
    id: str
    name: str
    description: str = ""
    model: str
    base_url: str | None = None
    system_prompt: str
    triggers: list[str] = Field(default_factory=list)
    priority: int = 0

    def match_score(self, text: str) -> int:
        best = 0
        for trigger in self.triggers:
            pattern = r"(?<!\w)" + re.escape(trigger.lower()) + r"(?!\w)"
            if re.search(pattern, text.lower()):
                best = max(best, len(trigger))
        return best
