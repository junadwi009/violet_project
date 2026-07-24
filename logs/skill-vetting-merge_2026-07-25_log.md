# Phase 3i — Import academic skills + skill vetting/merging

- **Date:** 2026-07-25
- **Track:** skills ecosystem / governance
- **Branch:** main
- **Author:** Claude Code

## What
Imported the 3 prompt-based academic-research-skills, and built a skill-governance capability:
a `skilltool` CLI to **vet** a candidate skill (good / redundant / low-quality) against the installed
library, and to **merge/upgrade** skills by combining them.

## Imported (academic-research-skills, CC-BY-NC 4.0 — LICENSE kept)
- `deep-research`, `academic-paper`, `academic-paper-reviewer` (top-level SKILL.md; instruction-only,
  so multi-agent depth flattens to the main prompt). Natural English `triggers:` added.
  Auto-detect verified: "literature review …" → deep-research; "review my paper" → academic-paper-reviewer;
  "write an academic paper …" → academic-paper. Now 15 agents total.
- **NonCommercial license** — fine for personal/local use; not for commercial.

## Is the Anthropic "artifacts" skill already available?
Yes, effectively. `web-artifacts-builder` builds **claude.ai-specific** React/Tailwind/shadcn artifacts.
Violet already generates HTML artifacts natively (`dashboard`, `interactive-chart`), and that skill's
CDN/React approach won't run in our no-network sandbox. The checker's LLM verdict confirmed:
**REDUNDANT (closest: skill:dashboard)**. Not imported.

## Skill vetting + merging
- `agents/vetting.py`: `build_library` (skills + agents), `nearest_matches` (keyword Jaccard + shared
  triggers), `rule_verdict` (novel/overlaps/redundant), `load_candidate` (parse + validity),
  `judge_candidate` (LLM quality/novelty verdict), `merge_skills` (LLM combine → clean SKILL.md).
- `tools/skilltool.py` CLI: `check <path> [--judge]`, `merge <ids|paths> --name --out`.
- `docs/SKILL_MANAGEMENT.md` — usage.

## Status
done — tests green, both CLIs live-verified.

## Verification
- `python -m pytest` → **68 passed** (+4 vetting: duplicate→redundant, novel→novel, empty rejected,
  valid parsed).
- Live `check --judge` on web-artifacts-builder: rule=novel (0.048 keyword overlap — different vocab),
  **LLM=REDUNDANT vs skill:dashboard** (shows why the LLM layer matters for semantic redundancy).
- Live `merge writer humanizer --name "Writer Pro"`: produced a coherent merged SKILL.md combining
  professional writing + anti-slop rules + the editing output format.

## Notes / next
- Rule-based overlap is keyword-only; `--judge` catches semantic redundancy. For bulk vetting, run
  check on each candidate and skip `redundant`.
- Optional: a `check`/`merge` API endpoint + UI; auto-run `check` on drop-in imports; batch `check` a
  whole repo.
