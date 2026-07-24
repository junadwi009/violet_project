# Phase 3b — More skills + specificity-based detection

- **Date:** 2026-07-25
- **Track:** skills / capabilities
- **Branch:** main
- **Author:** Claude Code

## What
Added 5 skills to the framework and made skill detection choose the most specific match.

## New skills (all safe artifacts)
- `interactive-chart` (html) — filterable chart/treemap/heatmap with a legend + filter controls,
  drawn inline (SVG/canvas). Covers "chart or map with legend + filter". Geographic tile maps need
  the network (blocked in the sandbox), so it renders schematic/region SVG, treemap, or heatmap and
  says so.
- `table` (html) — sortable/filterable/searchable data table + summary stats + written insights.
- `comparison` (html) — options × criteria matrix with scores, best-per-row highlight, and a verdict.
- `timeline` (html) — timeline/roadmap of phases/events/milestones with hover details + track filter.
- `calculator` (html) — interactive calculator/converter/planner widget with live outputs.

## Detection upgrade
- `Skill.match_score` uses word-boundary matching (so "chart" no longer matches "charter") and returns
  the longest matching trigger length. `SkillRegistry.detect` picks the highest score, so specific
  skills win (e.g. "interactive chart" → interactive-chart, plain "chart" → chart).

## Files
- `configs/skills/{interactive-chart,table,comparison,timeline,calculator}.json`
- `skills/schema.py` (match_score, word boundaries), `skills/registry.py` (best-match detect)
- `tests/test_skills.py` (+word-bounded match, +specificity routing)

## Status
done — tests green, live-verified.

## Verification
- `python -m pytest` → **43 passed** (+2 detection tests).
- Live (real key): `/api/skills` → 7 skills. "interactive chart … legend + filter" → self-contained
  html (SVG/canvas, filter controls, **no external refs**). "compare Notion vs Obsidian vs Roam" →
  self-contained comparison table (no external refs).

## Next
CSV/file upload as a data source; a "mind-map/flowchart" skill (inline SVG); persisting artifacts;
optional per-skill model selection.
