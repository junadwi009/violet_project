# Per-skill artifact display: simple artifacts render inline in chat

- **Date:** 2026-07-26
- **Track:** 1 Chat / 3 Skills
- **Branch:** feat/inline-artifact-display
- **Author:** Claude

## What
Skills now declare how their output is presented. `Skill.display` accepts
`"inline"` (render in the chat flow) or `"canvas"` (open in the side panel);
empty falls back to a per-kind default (`chartjs`/`docx`/`pptx` → inline,
`html` → canvas). `SkillEngine` stamps the resolved value onto every artifact,
`Artifact.display` carries it to the client, and `ChatTimeline` renders inline
artifacts in full instead of as a compact card. Inline artifacts keep a small
expand control so the canvas is still one click away.

Shipped assignment (12 skills):
- **inline:** chart, mindmap, comparison, timeline, minutes, documentation,
  presentation (pptx card), report (docx card)
- **canvas:** dashboard, calculator, interactive-chart, table

## Why
Requested: simple artifacts should appear in the conversation the way claude.ai
renders charts, rather than every artifact becoming an "Open in canvas" card.
A per-skill hint was chosen over a kind-based rule because the 9 `html` skills
range from a static SVG mindmap to a fully interactive dashboard — one flag per
skill is explicit and retunable by editing a single config file.

## Files touched
- `services/assistant-core/src/violet_assistant/skills/schema.py` (`display` + `resolved_display`)
- `services/assistant-core/src/violet_assistant/skills/generator.py` (stamp onto artifacts)
- `services/assistant-core/src/violet_assistant/schemas/chat.py` (`Artifact.display`)
- `configs/skills/*.json` (all 12 now declare `display`)
- `apps/web-client/src/lib/api.ts` (`Artifact.display`)
- `apps/web-client/src/components/ChatTimeline.tsx` (SHARED SEAM: inline vs card)
- `apps/web-client/src/components/ArtifactView.tsx` (expand-to-canvas control)
- `services/assistant-core/tests/test_skills.py` (4 tests)

## Interfaces / contracts changed
- `Skill.display: str = ""` + `Skill.resolved_display -> "inline" | "canvas"`.
- `Artifact.display: str = "canvas"` (defaults preserve prior behaviour for any
  artifact produced outside the skill engine).

## Status
done

## Verification
- `python -m pytest -q` → **146 passed** (incl. a guard that every shipped skill
  resolves to a valid display mode).
- `npm run build` → clean.
- Live: `POST /api/chat {skill_id: "chart"}` → `display: "inline"`; the browser
  renders a 780x390 chart **inside `<main>`** with no compact card and the canvas
  panel closed. Screenshot matches the requested claude.ai layout.
- Live: `skill_id: "dashboard"` → `display: "canvas"` (still opens the panel).

## Next
Retune any single skill by editing its `display` in `configs/skills/<id>.json` —
no code change needed.
