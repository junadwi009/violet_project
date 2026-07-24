# Imported skills (Anthropic SKILL.md format)

Drop community skills here and Violet loads them as **agents** automatically.

## How to import
1. Get a skill folder that contains a `SKILL.md` (e.g. from
   [anthropics/skills](https://github.com/anthropics/skills) or the Claude Scientific Skills repo).
2. Put it in its own subfolder here, e.g. `configs/agents/imported/<skill-name>/SKILL.md`.
3. Restart the backend. The skill appears in `GET /api/agents` and can be selected or auto-triggered.

## What gets imported
- `name` + `description` (frontmatter) → the agent's identity.
- The markdown body → the agent's system prompt (instructions).
- Optional `triggers:` / `keywords:` frontmatter (comma-separated) → auto-detection terms.
  Without them, the skill's name is used as the trigger (select it explicitly in Settings).

## Limits (instruction-only)
The importer runs the **instructions** of a SKILL.md. It does **not** execute a skill's bundled
scripts or load its extra resource files — those need a code sandbox we don't run. Prompt/instruction
skills (most writing, analysis, formatting, and workflow skills) work well; script-heavy skills won't.

Imported skills use the `AGENT_DEFAULT_MODEL` (default `nousresearch/hermes-4-70b`) unless the
frontmatter sets `model:`.
