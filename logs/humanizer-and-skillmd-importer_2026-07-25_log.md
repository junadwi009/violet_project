# Phase 3f — Humanizer agent (StopSlop) + SKILL.md importer

- **Date:** 2026-07-25
- **Track:** agents / skills ecosystem
- **Branch:** main
- **Author:** Claude Code

## What
Researched StopSlop, OpenManus, DeepAgents, and Claude Scientific Skills; adopted the two that fit
Violet's config-driven model. Added a Humanizer agent and an importer for Anthropic-format SKILL.md
skills. (OpenManus / DeepAgents are agent *frameworks/runtimes*, not skills — kept as design
reference only, not imported.)

## Humanizer agent (from StopSlop)
- `configs/agents/humanizer.json` — "Editor (Humanizer)" on `nousresearch/hermes-4-70b`. Strips
  AI-slop (banned phrases, structural anti-patterns, active voice, no em-dash) and scores output on
  5 dimensions (directness/rhythm/trust/authenticity/density, /50). `priority: 1`.
- Folded the anti-slop rules into the existing `writer.json` agent.

## SKILL.md importer
- `agents/skillmd.py` — `parse_skill_md`: parse Anthropic SKILL.md (frontmatter name/description +
  markdown body) → a Violet agent (body = system prompt, model = `AGENT_DEFAULT_MODEL` unless the
  frontmatter sets one, triggers from name + optional `triggers:`/`keywords:`). No PyYAML dep.
- `agents/registry.py` — also loads any `SKILL.md` under the agents dir (`rglob`), so dropping a skill
  folder into `configs/agents/imported/<name>/SKILL.md` registers it automatically.
- `config.py` — `AGENT_DEFAULT_MODEL`. `main.py` passes it to the registry.
- `configs/agents/imported/README.md` (how to import) + a working example
  `configs/agents/imported/standup/SKILL.md`.
- Instruction-only: runs a skill's SKILL.md prompt; does NOT execute bundled scripts/resources
  (no code sandbox). Prompt/analysis/writing/workflow skills work; script-heavy ones don't.

## Interfaces / contracts
- No API changes. Imported skills appear in `GET /api/agents` alongside native agents. `Settings`
  gained `agent_default_model` (defaulted). No breaking changes.

## Status
done — tests green, live-verified.

## Verification
- `python -m pytest` → **64 passed** (+2: parse_skill_md, registry loads imported SKILL.md).
- Live (real key): `/api/agents` lists 6 (4 native + humanizer + imported standup-update).
  Humanizer turned "In today's fast-paced world … truly revolutionizes the very fabric …" into
  "Our solution revolutionizes productivity by streamlining workflows." + score 44/50. Imported
  standup SKILL.md produced Yesterday/Today/Blockers (auto-detect + explicit).
- Docker: image rebuilt (see session).

## Assessment (for the record)
- StopSlop → adopted (Humanizer + Writer upgrade). ✅
- Anthropic/Scientific SKILL.md skills → adopted via importer (instruction-only). ✅
- OpenManus / DeepAgents → agent frameworks, not skills; not imported. Reference for a future
  autonomous orchestrator (chain skills, code sandbox) only.

## Next
Optional: a converter CLI to bulk-import a whole skills repo; auto-derive better triggers; a
sandboxed runtime if we ever want script-backed skills (the OpenManus/DeepAgents direction).
