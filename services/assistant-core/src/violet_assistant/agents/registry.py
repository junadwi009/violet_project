from __future__ import annotations

import json
from pathlib import Path

from violet_assistant.agents.schema import Agent


class AgentRegistry:
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir

    def list_agents(self) -> list[Agent]:
        if not self.config_dir.exists():
            return []
        agents: list[Agent] = []
        for path in sorted(self.config_dir.glob("*.json")):
            try:
                agents.append(Agent.model_validate(json.loads(path.read_text(encoding="utf-8"))))
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
