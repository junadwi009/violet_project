# Phase 3k — Merge → Install button

- **Date:** 2026-07-25
- **Track:** skills governance
- **Branch:** main
- **Author:** Claude Code

## What
Added a one-click **Install** for skills built in the Skill Lab: it writes the SKILL.md into
`configs/agents/imported/<slug>/` and the skill is live immediately (the agent registry re-reads the
folder every request — no restart).

## Backend
- `agents/vetting.py`: `install_skill(skill_md, imported_dir, default_model)` — validates the SKILL.md,
  writes `imported_dir/<slug>/SKILL.md` (slug sanitized → no path traversal), returns id/name/path/updated.
- `routes/skill_admin.py`: `POST /api/skills/install` (body `{skill_md}`); router now takes `imported_dir`.
- `main.py`: passes `agents_dir/"imported"`.
- `docker-compose.yml`: bind-mount `./configs/agents/imported` so runtime installs persist to the host repo.

## Frontend
- `lib/api.ts`: `installSkill`.
- `components/SkillLab.tsx`: after a merge, an **Install skill** button (writes it live) + a "✓ Installed
  as … — live now" confirmation; the library refreshes so the new skill shows in the picker.

## Interfaces / contracts
- New `POST /api/skills/install` (additive). `create_skill_admin_router` gained `imported_dir`.
  No breaking changes.

## Status
done — tests green, endpoint live-verified.

## Verification
- `python -m pytest` → **73 passed** (+2: install writes + registry loads it live; invalid rejected).
- Backend smoke (scratch agents dir): 0 agents → `POST /api/skills/install` (Meeting Recap) → 1 agent
  (`meeting-recap`) in the same process, **no restart**. Frontend `npm run build` clean.
- Docker: stack rebuilt; imported dir bind-mounted for persistence.

## Next
Optional: install-with-vet (block install if the checker says redundant), edit-before-install, or an
"uninstall" action.
