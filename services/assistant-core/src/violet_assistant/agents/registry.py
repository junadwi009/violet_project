from __future__ import annotations

import json
from pathlib import Path

from violet_assistant.agents.schema import Agent
from violet_assistant.agents.skillmd import parse_skill_md


class AgentRegistry:
    def __init__(
        self,
        config_dir: Path,
        default_model: str = "nousresearch/hermes-4-70b",
        resolver=None,
    ) -> None:
        self.config_dir = config_dir
        self.default_model = default_model
        self._resolver = resolver

    def _effective_default_model(self) -> str:
        if self._resolver is None:
            return self.default_model
        return self._resolver.resolve("agent_default_model")

    def list_agents(self) -> list[Agent]:
        if not self.config_dir.exists():
            return []
        agents: list[Agent] = []
        # Native Violet agents (JSON).
        for path in sorted(self.config_dir.glob("*.json")):
            try:
                agents.append(Agent.model_validate(json.loads(path.read_text(encoding="utf-8"))))
            except (ValueError, KeyError):
                continue
        # Imported Anthropic-format skills: any SKILL.md under the agents dir (e.g. imported/<name>/SKILL.md).
        # Resolved once per listing so every skill in one listing agrees on the default.
        default_model = self._effective_default_model()
        for path in sorted(self.config_dir.rglob("SKILL.md")):
            try:
                agents.append(
                    parse_skill_md(
                        path.read_text(encoding="utf-8"),
                        fallback_id=path.parent.name,
                        default_model=default_model,
                    )
                )
            except (ValueError, KeyError):
                continue
        return agents

    def get(self, agent_id: str | None) -> Agent | None:
        if not agent_id:
            return None
        for agent in self.list_agents():
            if agent.id == agent_id:
                return agent
        return None

    def detect(self, text: str) -> Agent | None:
        best: Agent | None = None
        best_key = (0, 0)
        for agent in self.list_agents():
            score = agent.match_score(text)
            if score == 0:
                continue
            key = (agent.priority, score)
            if key > best_key:
                best_key = key
                best = agent
        return best
