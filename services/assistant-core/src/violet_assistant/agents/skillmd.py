from __future__ import annotations

import re

from violet_assistant.agents.schema import Agent


# Words too generic to anchor a trigger on. Kept small and English-focused (Anthropic descriptions
# are English). We only ever emit MULTI-WORD triggers from descriptions, so this mainly trims noise.
_STOPWORDS = {
    "a", "an", "and", "any", "are", "as", "at", "be", "benefit", "by", "can", "create",
    "creating", "for", "from", "guide", "guidance", "have", "having", "help", "helps", "how",
    "in", "into", "is", "it", "its", "like", "make", "making", "may", "of", "on", "or", "other",
    "should", "skill", "so", "some", "sort", "such", "that", "the", "their", "them", "then",
    "these", "this", "to", "use", "used", "user", "uses", "using", "want", "when", "which",
    "will", "with", "you", "your", "via", "etc", "e", "g", "apply", "applies", "based",
}


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


def _derive_triggers(description: str, limit: int = 6) -> list[str]:
    """Derive specific multi-word triggers from a skill description.

    Uses adjacent pairs of content words (bigrams), which are specific enough to avoid the
    false-positive problem that single generic words ('report', 'design') cause.
    """
    words = re.findall(r"[a-z][a-z0-9+]*", description.lower())
    triggers: list[str] = []
    seen: set[str] = set()
    for first, second in zip(words, words[1:]):
        if first in _STOPWORDS or second in _STOPWORDS:
            continue
        if len(first) < 3 or len(second) < 3:
            continue
        phrase = f"{first} {second}"
        if phrase not in seen:
            seen.add(phrase)
            triggers.append(phrase)
        if len(triggers) >= limit:
            break
    return triggers


def parse_skill_md(text: str, fallback_id: str, default_model: str) -> Agent:
    """Convert an Anthropic-format SKILL.md into a Violet agent.

    Frontmatter `name`/`description` become the identity; the body becomes the system prompt; the
    model defaults to `default_model`. Triggers come from (a) explicit `triggers`/`keywords`
    frontmatter, (b) the skill name as a phrase, and (c) multi-word phrases derived from the
    description — so imported skills can auto-detect, not only be selected explicitly.
    """
    meta, body = _parse_frontmatter(text)
    name = meta.get("name") or fallback_id
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or fallback_id
    description = meta.get("description", "")

    triggers: list[str] = []
    seen: set[str] = set()

    def add(trigger: str) -> None:
        normalized = trigger.strip().lower()
        if normalized and normalized not in seen and len(normalized) >= 4:
            seen.add(normalized)
            triggers.append(normalized)

    for key in ("triggers", "keywords"):
        if meta.get(key):
            for trigger in meta[key].split(","):
                add(trigger)
    add(re.sub(r"[^a-z0-9]+", " ", name.lower()).strip())
    for trigger in _derive_triggers(description):
        add(trigger)

    system_prompt = body or description or name
    return Agent(
        id=slug,
        name=name,
        description=description[:200],
        model=meta.get("model") or default_model,
        system_prompt=system_prompt,
        triggers=triggers[:10],
        priority=0,
    )
