# Phase 3 — Skills Framework + Artifacts (charts / dashboards / analysis)

**Date:** 2026-07-25
**Status:** Approved via brainstorming
**Builds on:** Phase 1/2 (OpenRouter cascade).

## Goal
Give Violet Claude-like capability to generate **charts**, **interactive report dashboards**, and
**data analysis**, via a small **skills framework** that's extensible (add a skill by dropping a JSON).

## Decisions
1. **Rendering (both):** simple charts = structured **Chart.js spec** rendered by a bundled library
   (no code execution — safe); full dashboards/reports = **self-contained HTML** rendered in a
   **locked-down sandboxed iframe** (`sandbox="allow-scripts"`, no same-origin; CSP
   `default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:` — blocks
   network so private data can't be exfiltrated). HTML artifacts must be self-contained (inline JS/SVG).
2. **Artifact model:** `qwen/qwen3-coder` via OpenRouter (`ARTIFACT_MODEL`, swappable). Cheap, strong
   at HTML/JS/charts.
3. **Skills are config-driven:** `configs/skills/*.json` (id, name, description, kind, triggers, prompt).
   Flagship: `chart` (kind `chartjs`), `dashboard` (kind `html`). Extensible — this is where curated
   skills from Claude/ChatGPT/community/GitHub get added over time.
4. **Detection:** rule-based keyword match on the user message (cheap, no extra call). Skills are
   active only when an OpenRouter key is configured; `mock`/offline requests skip skills.

## Data flow
1. `SkillRegistry` loads skill JSONs. `detect(message)` → matching `Skill | None` (keyword rules).
2. If a skill matches (and not mock): call the **artifact model** with the skill prompt + the user
   message/data. The model returns a short intro line + one fenced artifact block:
   - chart: ```chartjs\n{Chart.js config JSON}\n```
   - dashboard: ```html\n<self-contained html>\n```
3. `parse_artifacts(text)` splits the intro text from the artifact block(s) →
   `Artifact{id, kind, title, spec|html}`.
4. `ChatResponse.artifacts: list[Artifact]` (text stays the intro). No skill → normal cascade/provider.

## Backend
- `config.py`: `ARTIFACT_MODEL` (default `qwen/qwen3-coder`), `SKILLS_CONFIG_DIR` (default
  `<repo_root>/configs/skills`). New fields have dataclass defaults.
- `skills/` package: `schema.py` (Skill), `registry.py` (load), `detector.py` (keyword match),
  `generator.py` (call artifact model, parse artifact blocks).
- `schemas/chat.py`: `Artifact` + `ChatResponse.artifacts`.
- `ChatOrchestrator`: optional `skill_engine`; if a skill is detected on a non-mock request, generate
  the artifact and return it; else existing path. `GET /api/skills` lists skills.

## Frontend
- Dep: `chart.js`.
- `lib/api.ts`: `Artifact` type, `ChatResponse.artifacts`, `fetchSkills`; `ChatMessage.artifacts`.
- `components/ArtifactView.tsx`: `chartjs` → `<canvas>` via Chart.js; `html` → sandboxed `<iframe srcdoc>`.
- `ChatTimeline` renders artifacts beneath the assistant message. A small "Skills" hint in the composer
  / settings lists available skills.

## Testing
- Unit (no network): skill detection by keyword; artifact parsing (chartjs + html blocks; intro split;
  no-artifact passthrough). Existing suite stays green.
- Live smoke (real key): "bar chart of [data]" → chartjs artifact; "interactive dashboard of [data]" →
  html artifact.

## Out of scope (later)
File/CSV upload as data source (data comes from the conversation for now); more curated skills;
persisting artifacts; streaming.
