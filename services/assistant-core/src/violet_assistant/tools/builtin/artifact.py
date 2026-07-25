from __future__ import annotations

from violet_assistant.tools.base import ToolResult


class CreateArtifactTool:
    name = "create_artifact"
    description = (
        "Produce a rendered artifact (chart, table, diagram, document) using one "
        "of the assistant's skills. Use when a visual or downloadable output "
        "answers the question better than prose."
    )
    parameters = {
        "type": "object",
        "properties": {
            "skill_id": {
                "type": "string",
                "description": "Skill id, e.g. chart, table, mindmap, timeline, report.",
            },
            "request": {
                "type": "string",
                "description": "Full instruction for the skill, including the data.",
            },
        },
        "required": ["skill_id", "request"],
    }
    risk = "low"
    required_flags: tuple[str, ...] = ()

    def __init__(self, skill_registry, skill_engine) -> None:
        self.skill_registry = skill_registry
        self.skill_engine = skill_engine

    async def run(self, args: dict) -> ToolResult:
        skill_id = str(args.get("skill_id", "")).strip()
        request = str(args.get("request", "")).strip()
        skill = self.skill_registry.get(skill_id)
        if skill is None:
            return ToolResult(
                text=f"Unknown skill_id '{skill_id}'.", error="unknown skill"
            )
        if not request:
            return ToolResult(text="request is required", error="missing request")
        intro, artifacts = await self.skill_engine.generate(skill, request)
        if not artifacts:
            return ToolResult(text=intro or "The skill produced no artifact.")
        return ToolResult(
            text=f"Created {len(artifacts)} artifact(s) with the {skill.name} skill.",
            artifacts=artifacts,
        )
