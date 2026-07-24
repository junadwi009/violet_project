from __future__ import annotations

import json
import re
from uuid import uuid4

from violet_assistant.llm.base import LLMOptions, LLMProvider, Message
from violet_assistant.skills.schema import Skill


_BLOCK_RE = re.compile(r"```(chartjs|html)[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_artifacts(text: str) -> tuple[str, list[dict]]:
    """Split model output into (intro_text, artifacts). Pure — no network, unit-testable."""
    artifacts: list[dict] = []

    def _take(match: re.Match) -> str:
        kind = match.group(1).lower()
        body = match.group(2).strip()
        if kind == "chartjs":
            try:
                spec = json.loads(body)
            except json.JSONDecodeError:
                return ""  # drop an unparseable chart block
            artifacts.append(
                {"id": str(uuid4()), "kind": "chartjs", "title": "", "spec": spec, "html": None}
            )
        else:  # html
            artifacts.append(
                {"id": str(uuid4()), "kind": "html", "title": "", "spec": None, "html": body}
            )
        return ""

    intro = _BLOCK_RE.sub(_take, text).strip()
    return intro, artifacts


class SkillEngine:
    """Generates renderable artifacts for a matched skill using the artifact (coding) model."""

    def __init__(self, provider: LLMProvider, model: str) -> None:
        self.provider = provider
        self.model = model

    async def generate(self, skill: Skill, user_content: str) -> tuple[str, list[dict]]:
        response = await self.provider.chat(
            [
                Message(role="system", content=skill.prompt),
                Message(role="user", content=user_content),
            ],
            LLMOptions(model=self.model, temperature=0.2),
        )
        intro, artifacts = parse_artifacts(response.text)
        if not artifacts:
            # Model didn't emit a well-formed artifact; return its text as-is.
            return response.text.strip(), []
        if not intro:
            intro = f"Here is the {skill.name.lower()} you asked for."
        for artifact in artifacts:
            artifact["title"] = artifact["title"] or skill.name
        return intro, artifacts
