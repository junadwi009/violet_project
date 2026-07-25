from __future__ import annotations

from violet_assistant.config import Settings
from violet_assistant.tools.base import RISK_ORDER


class ToolRegistry:
    """The set of tools an agent may call. Built once per run and never mutated.

    Freezing the allowlist is a security control (SECURITY_RULES #3): no tool
    result can add a tool or widen permissions mid-loop.
    """

    def __init__(self, tools: list) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def get(self, name: str):
        return self._tools.get(name)

    def enabled(self) -> list:
        return list(self._tools.values())

    def specs(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]


def requires_confirmation(tool, settings: Settings) -> bool:
    """Server-side gate. Never derived from model output."""
    if not settings.require_confirmation_for_risky_tools:
        return False
    threshold = RISK_ORDER.get(settings.tool_confirm_threshold, RISK_ORDER["high"])
    return RISK_ORDER.get(tool.risk, RISK_ORDER["critical"]) >= threshold


def flags_satisfied(tool, settings: Settings) -> bool:
    return all(
        getattr(settings, flag, False) for flag in getattr(tool, "required_flags", ())
    )


def create_tool_registry(
    settings: Settings,
    *,
    retriever=None,
    skill_registry=None,
    skill_engine=None,
    web_provider=None,
    web_model: str = "",
) -> ToolRegistry:
    """Build the tools whose dependencies exist AND whose flags are satisfied.

    A tool that fails either check is never constructed, so it never reaches
    `specs()` — the model cannot request what it cannot see.
    """
    from violet_assistant.tools.builtin.artifact import CreateArtifactTool
    from violet_assistant.tools.builtin.knowledge import KnowledgeSearchTool
    from violet_assistant.tools.builtin.web import FetchUrlTool, WebSearchTool

    candidates = [FetchUrlTool()]
    if retriever is not None:
        candidates.append(KnowledgeSearchTool(retriever))
    if skill_registry is not None and skill_engine is not None:
        candidates.append(CreateArtifactTool(skill_registry, skill_engine))
    if web_provider is not None and web_model:
        candidates.append(WebSearchTool(web_provider, web_model))
    return ToolRegistry([t for t in candidates if flags_satisfied(t, settings)])
