# Phase 3 — Skills framework + artifacts (charts / dashboards)

- **Date:** 2026-07-25
- **Track:** skills / capabilities
- **Branch:** main
- **Author:** Claude Code

## What
Added a config-driven skills framework and an artifact pipeline so Violet can generate **charts**
(Chart.js specs) and **interactive HTML dashboards/reports** — the "like Claude" capability. Design:
`docs/superpowers/specs/2026-07-25-skills-artifacts-design.md`.

## Why
User asked for chart / interactive report dashboard / analysis generation like Claude Artifacts, and
for a skills system that can grow with curated skills from Claude/ChatGPT/community/GitHub.

## Backend
- `configs/skills/chart.json`, `configs/skills/dashboard.json` — skill defs (triggers + generation
  prompt). This directory is where future community skills get dropped in.
- `skills/` package: `schema.py` (Skill), `registry.py` (load + rule-based `detect`), `generator.py`
  (`SkillEngine` calls the artifact model; `parse_artifacts` splits intro text from ```chartjs / ```html
  blocks — pure/testable).
- `schemas/chat.py`: `Artifact` + `ChatResponse.artifacts`.
- `ChatOrchestrator`: on a non-mock request whose text matches a skill trigger, generate the artifact
  via the artifact model and return it (else existing cascade/provider path).
- `config.py`: `ARTIFACT_MODEL` (default `qwen/qwen3-coder`), `ARTIFACT_BASE_URL/API_KEY`,
  `SKILLS_CONFIG_DIR`. Skills activate only when an artifact key is present.
- `GET /api/skills` lists available skills + enabled flag. Wired in `main.py`.

## Rendering (safety)
- **chartjs**: parent app renders with bundled `chart.js` (no code execution).
- **html**: sandboxed `<iframe srcdoc sandbox="allow-scripts">` with a strict CSP
  (`default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:;
  connect-src 'none'`) — LLM-written dashboards run but cannot reach the app or the network.
  Skill prompt requires fully self-contained HTML (no external libs/CDN/fetch).
- `components/ArtifactView.tsx` renders both; `ChatTimeline` shows artifacts under the assistant
  message; `App` attaches `response.artifacts`. EmptyState quick-prompts surface the new skills.

## Interfaces / contracts
- `ChatResponse` gained `artifacts`. New `GET /api/skills`. `Settings` gained artifact/skills fields
  (all defaulted). `ChatOrchestrator` gained optional `skill_registry`/`skill_engine`. No breaking changes.

## Status
done — tests green, live-verified against real OpenRouter.

## Verification
- `python -m pytest` → **41 passed** (+6: skill detection, chartjs/html parsing, invalid-json drop,
  passthrough). Backend import smoke OK. `npm run build` clean.
- Live (local uvicorn, real key):
  - `GET /api/skills` → chart + dashboard, enabled.
  - "bar chart of sales Jan..Apr" → **chartjs artifact** (type=bar, correct labels) + intro.
  - "interactive dashboard of 3 products…" → **html artifact** (12.8 KB, self-contained,
    **no external network refs** — safe for the sandbox).

## Next
More curated skills (table/CSV analysis, timeline, comparison, mind-map), CSV/file upload as a data
source, persisting artifacts, and moving the persona layer to a local host for full privacy.
