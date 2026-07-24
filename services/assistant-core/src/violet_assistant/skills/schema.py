from __future__ import annotations

from pydantic import BaseModel, Field


class Skill(BaseModel):
    id: str
    name: str
    description: str = ""
    kind: str  # "chartjs" | "html"
    triggers: list[str] = Field(default_factory=list)
    prompt: str

    def matches(self, text: str) -> bool:
        lowered = text.lower()
        return any(trigger.lower() in lowered for trigger in self.triggers)
