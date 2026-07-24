# Phase 3j — Skill governance as API + UI (Skill Lab)

- **Date:** 2026-07-25
- **Track:** skills governance
- **Branch:** main
- **Author:** Claude Code

## What
Exposed the skill-governance toolkit (check / merge / batch) — previously CLI-only — as HTTP APIs and
a "Skill Lab" UI in the web client.

## Backend
- `agents/vetting.py`: `candidate_from_text` (parse+validate SKILL.md text), `resolve_ref` (id →
  Agent from skills or agents registry; skills wrapped for merging). `load_candidate` now delegates.
- `routes/skill_admin.py`:
  - `GET  /api/skills/library` — installed skills+agents (id, kind, name, description) + judge_enabled.
  - `POST /api/skills/check` — `{content, judge}` → rule verdict + nearest matches + optional LLM verdict.
  - `POST /api/skills/merge` — `{refs[], name}` → `{skill_md}` (LLM combine).
  - `POST /api/skills/batch` — `{items[{id,content}], judge}` → per-item rows + invalid list.
- `main.py`: builds an admin LLM provider (OpenRouter) and wires the router.

## Frontend
- `lib/api.ts`: `fetchSkillLibrary`, `checkSkill`, `mergeSkills` (+ types).
- `components/SkillLab.tsx`: modal with **Check** tab (paste SKILL.md → rule + LLM verdict + nearest)
  and **Merge** tab (pick 2+ from the library → merged SKILL.md with Copy). Opened from a new
  FlaskConical button in `FloatingTools`; wired in `App`.

## Interfaces / contracts
- New `GET /api/skills/library`, `POST /api/skills/{check,merge,batch}` (additive). No breaking changes.

## Status
done — tests green, endpoints smoke-verified, frontend builds.

## Verification
- `python -m pytest` → **71 passed** (+2: candidate_from_text valid/invalid, resolve_ref both registries).
- Backend smoke (local uvicorn): `/api/skills/library` → 29 items, judge_enabled true;
  `/api/skills/check` on a fake "Chart Maker" → rule=redundant, nearest chart @ 0.438.
- Frontend `npm run build` clean.
- Docker: full stack rebuilt (see session).

## Next
Optional: a batch UI tab (paste/upload multiple SKILL.md); install-a-merged-skill button that writes
to configs/agents/imported/; auth-gate the admin endpoints for multi-user deploys.
