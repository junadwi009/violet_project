from __future__ import annotations

import re

from violet_assistant.agents.schema import Agent


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse simple `key: value` YAML frontmatter (Anthropic SKILL.md style). No PyYAML dep."""
    if not text.startswith("---"):
        return {}, text.strip()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text.strip()
    meta: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        meta[key.strip().lower()] = value.strip().strip('"').strip("'")
    return meta, parts[2].strip()


def parse_skill_md(text: str, fallback_id: str, default_model: str) -> Agent:
    """Convert an Anthropic-format SKILL.md into a Violet agent.

    The frontmatter `name`/`description` become the agent identity; the markdown body becomes the
    system prompt; the model defaults to `default_model` (SKILL.md doesn't specify one). Optional
    `triggers`/`keywords` frontmatter (comma-separated) add auto-detection terms.
    """
    meta, body = _parse_frontmatter(text)
    name = meta.get("name") or fallback_id
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or fallback_id
    description = meta.get("description", "")

    triggers = [name.lower()]
    for key in ("triggers", "keywords"):
        if meta.get(key):
            triggers += [t.strip().lower() for t in meta[key].split(",") if t.strip()]
    # de-dup while preserving order
    seen: set[str] = set()
    triggers = [t for t in triggers if not (t in seen or seen.add(t))]

    system_prompt = body or description or name
    return Agent(
        id=slug,
        name=name,
        description=description[:200],
        model=meta.get("model") or default_model,
        system_prompt=system_prompt,
        triggers=triggers,
        priority=0,
    )
