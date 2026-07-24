from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from violet_assistant.agents.registry import AgentRegistry
from violet_assistant.agents.schema import Agent
from violet_assistant.agents.skillmd import parse_skill_md
from violet_assistant.llm.base import LLMOptions, LLMProvider, Message
from violet_assistant.skills.registry import SkillRegistry


_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "for", "with", "when", "use", "using", "it",
    "this", "that", "any", "all", "your", "you", "will", "can", "should", "may", "be", "is",
    "are", "on", "in", "at", "by", "from", "as", "into", "help", "skill", "agent", "make",
    "create", "creating", "guide", "based", "not", "user", "users",
}


def _terms(name: str, description: str, triggers: list[str]) -> set[str]:
    text = f"{name} {description} {' '.join(triggers)}".lower()
    words = re.findall(r"[a-z][a-z0-9+]{2,}", text)
    return {w for w in words if w not in _STOP}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class LibraryEntry:
    id: str
    kind: str  # "skill" | "agent"
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    terms: set[str] = field(default_factory=set)


def build_library(
    skill_registry: SkillRegistry | None, agent_registry: AgentRegistry | None
) -> list[LibraryEntry]:
    entries: list[LibraryEntry] = []
    for s in skill_registry.list_skills() if skill_registry else []:
        entries.append(
            LibraryEntry(s.id, "skill", s.name, s.description, list(s.triggers),
                         _terms(s.name, s.description, list(s.triggers)))
        )
    for a in agent_registry.list_agents() if agent_registry else []:
        entries.append(
            LibraryEntry(a.id, "agent", a.name, a.description, list(a.triggers),
                         _terms(a.name, a.description, list(a.triggers)))
        )
    return entries


@dataclass
class Match:
    entry: LibraryEntry
    similarity: float
    shared_triggers: list[str]


def nearest_matches(
    candidate: Agent, library: list[LibraryEntry], top: int = 3
) -> list[Match]:
    cand_terms = _terms(candidate.name, candidate.description, list(candidate.triggers))
    cand_trigs = {t.lower() for t in candidate.triggers}
    matches: list[Match] = []
    for entry in library:
        if entry.id == candidate.id:
            continue
        shared = sorted(cand_trigs & {t.lower() for t in entry.triggers})
        matches.append(Match(entry, round(_jaccard(cand_terms, entry.terms), 3), shared))
    matches.sort(key=lambda m: (m.similarity, len(m.shared_triggers)), reverse=True)
    return matches[:top]


def candidate_from_text(content: str, fallback_id: str, default_model: str) -> Agent:
    """Parse SKILL.md text into an Agent. Raises ValueError if clearly invalid."""
    candidate = parse_skill_md(content, fallback_id=fallback_id, default_model=default_model)
    if not candidate.name.strip() or len(candidate.system_prompt.strip()) < 40:
        raise ValueError("Skill has no meaningful instructions (empty or too short).")
    return candidate


def load_candidate(path: str | Path, default_model: str) -> Agent:
    """Parse a candidate SKILL.md file into an Agent. Raises ValueError if clearly invalid."""
    p = Path(path)
    return candidate_from_text(p.read_text(encoding="utf-8"), p.parent.name, default_model)


def resolve_ref(ref: str, skill_registry, agent_registry, default_model: str) -> Agent | None:
    """Resolve an id to an Agent from either registry (skills wrapped as Agents for merging)."""
    agent = agent_registry.get(ref) if agent_registry else None
    if agent is not None:
        return agent
    for skill in skill_registry.list_skills() if skill_registry else []:
        if skill.id == ref:
            return Agent(
                id=skill.id,
                name=skill.name,
                model=default_model,
                system_prompt=skill.prompt,
                description=skill.description,
                triggers=list(skill.triggers),
            )
    return None


def rule_verdict(candidate: Agent, matches: list[Match]) -> dict:
    """Offline verdict from rule-based overlap: duplicate / overlaps / novel."""
    if not matches:
        return {"verdict": "novel", "reason": "No similar skill in the library."}
    best = matches[0]
    if best.similarity >= 0.45 or len(best.shared_triggers) >= 2:
        return {
            "verdict": "redundant",
            "reason": f"Duplicates {best.entry.kind} '{best.entry.id}' "
            f"(similarity {best.similarity}, shared triggers {best.shared_triggers or 'none'}).",
        }
    if best.similarity >= 0.25:
        return {
            "verdict": "overlaps",
            "reason": f"Overlaps {best.entry.kind} '{best.entry.id}' "
            f"(similarity {best.similarity}). Review before installing.",
        }
    return {"verdict": "novel", "reason": f"Low overlap (nearest {best.entry.id} @ {best.similarity})."}


def batch_report(
    candidates: list[Agent], library: list[LibraryEntry], installed_ids: set[str]
) -> list[dict]:
    """Rule-based verdict row per candidate (offline). CLI adds an optional LLM verdict."""
    rows: list[dict] = []
    for candidate in candidates:
        matches = nearest_matches(candidate, library)
        verdict = rule_verdict(candidate, matches)
        rows.append(
            {
                "id": candidate.id,
                "installed": candidate.id in installed_ids,
                "rule": verdict["verdict"],
                "nearest": matches[0].entry.id if matches else None,
                "similarity": matches[0].similarity if matches else 0.0,
            }
        )
    return rows


async def judge_candidate(
    candidate: Agent, library: list[LibraryEntry], provider: LLMProvider, model: str
) -> dict:
    """LLM judgment of quality + novelty vs the existing library (needs a provider)."""
    lib = "\n".join(f"- {e.kind}:{e.id} — {e.name}: {e.description[:120]}" for e in library)
    user = (
        "Existing skill/agent library:\n" + lib + "\n\n"
        f"Candidate skill:\nname: {candidate.name}\ndescription: {candidate.description}\n"
        f"instructions (excerpt): {candidate.system_prompt[:1200]}\n\n"
        "Decide whether installing the candidate is worthwhile or redundant/low-quality, given the "
        "library. Reply with STRICT JSON only: "
        '{"verdict": "keep" | "redundant" | "low_quality", "closest": "<id or none>", '
        '"reason": "<one or two sentences>"}'
    )
    response = await provider.chat(
        [
            Message(role="system", content="You are a precise skill reviewer. Output only JSON."),
            Message(role="user", content=user),
        ],
        LLMOptions(model=model, temperature=0.0),
    )
    return _parse_json(response.text)


async def merge_skills(
    skills: list[Agent], new_name: str, provider: LLMProvider, model: str
) -> str:
    """Combine several skills into one improved SKILL.md (LLM-assisted)."""
    blocks = "\n\n".join(
        f"### Skill {i + 1}: {s.name}\n{s.system_prompt[:4000]}" for i, s in enumerate(skills)
    )
    user = (
        f"Combine the skills below into ONE improved skill named '{new_name}'. Keep the best, most "
        "useful instructions from each, remove redundancy, resolve conflicts, and make it coherent. "
        "Output ONLY a valid SKILL.md: frontmatter with name, description (one line, includes when to "
        "use it), and a comma-separated triggers line; then the merged instruction body.\n\n" + blocks
    )
    response = await provider.chat(
        [
            Message(role="system", content="You create clean, coherent Agent SKILL.md files."),
            Message(role="user", content=user),
        ],
        LLMOptions(model=model, temperature=0.3),
    )
    text = response.text.strip()
    # Strip a wrapping ```markdown ... ``` fence if the model added one.
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def _parse_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"verdict": "unknown", "reason": text.strip()[:200]}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"verdict": "unknown", "reason": text.strip()[:200]}
