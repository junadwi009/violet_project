# Managing skills & agents

Violet's skills (`configs/skills/*.json`, produce artifacts) and agents
(`configs/agents/*.json` + imported `SKILL.md`) are config-driven. This is how to add, vet, and
combine them.

## Import a skill (Anthropic SKILL.md format)
Drop a skill folder into `configs/agents/imported/<name>/SKILL.md` and restart the backend. It loads
as an agent (frontmatter `name`/`description` → identity, body → prompt). Add a `triggers:` line to
the frontmatter for reliable auto-detection; otherwise triggers are derived from the description.

## Vet a skill before installing it
Check whether a candidate is worth installing or is redundant/low-quality vs what you already have:

```bash
# rule-based (offline): validity + keyword/trigger overlap with the installed library
PYTHONPATH=services/assistant-core/src python -m violet_assistant.tools.skilltool check path/to/SKILL.md

# add an LLM verdict (needs OPENROUTER_API_KEY) — catches semantic redundancy the keywords miss
PYTHONPATH=services/assistant-core/src python -m violet_assistant.tools.skilltool check path/to/SKILL.md --judge
```

The rule pass reports the nearest existing skills + a verdict (`novel` / `overlaps` / `redundant`).
The `--judge` pass asks a model whether to `keep` / `redundant` / `low_quality` given your library.
Example: the Anthropic `web-artifacts-builder` skill checks as **redundant** — Violet already has the
`dashboard` skill (and that skill's React/shadcn approach won't run in our no-network sandbox anyway).

## Upgrade a skill by combining skills
Merge two or more skills/agents into one improved SKILL.md (keeps the best of each, removes overlap):

```bash
PYTHONPATH=services/assistant-core/src python -m violet_assistant.tools.skilltool \
  merge writer humanizer --name "Writer Pro" --out configs/agents/imported/writer-pro/SKILL.md
```

`merge` accepts skill/agent ids (from the registries) or paths to SKILL.md files. Review the output,
then restart the backend to load the new skill.

## Rule of thumb
Before bulk-importing a repo of skills, `check` each one: skip anything flagged `redundant` (you
already have a better native equivalent) or that depends on scripts/CDNs our instruction-only importer
and sandbox don't run.
