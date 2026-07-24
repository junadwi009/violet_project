# Phase 3g — Bulk import anthropics/skills + assess 3 more sources

- **Date:** 2026-07-25
- **Track:** skills ecosystem
- **Branch:** main
- **Author:** Claude Code

## What
Bulk-imported a batch of `anthropics/skills` (Apache-2.0) into Violet via the SKILL.md importer, and
assessed book-to-skill, notebooklm-py, and academic-research-skills.

## Imported (configs/agents/imported/, Apache-2.0, LICENSE.txt kept for attribution)
- `internal-comms` — internal communications writing
- `doc-coauthoring` — collaborative document authoring
- `frontend-design` — frontend/UI design guidance
- `mcp-builder` — building MCP servers
- `skill-creator` — creating new skills
- `canvas-design` — canvas/visual design
Skipped: docx/pptx/xlsx/pdf/webapp-testing/slack-gif (script-heavy — we already do docs natively;
scripts don't run in the instruction-only importer) and `brand-guidelines` (Anthropic-brand-specific,
not useful for the user's own product).

Result: 12 agents total load (4 native task agents + writer + humanizer + standup + 6 imported).
Imported skills are explicit-select (their trigger is the skill name); pick them in Settings.

## Assessment of the 3 sources
- **book-to-skill** (multiple repos; Apache/MIT) — converts books (PDF/EPUB/MD) into Claude skills.
  Useful *concept*; partly replicable natively — Violet already extracts PDFs/DOCX (ingestion) and
  imports SKILL.md, so a "book → SKILL.md distiller" agent + our ingestion could reproduce its value.
  The tool itself relies on local extraction scripts our importer won't run. Verdict: adopt the idea
  as a native pipeline later; don't import the tool as-is.
- **notebooklm-py** (MIT) — unofficial Python API for Google NotebookLM (needs Google auth). Generates
  audio/video/slides/quizzes/flashcards/mind-maps/reports. Verdict: NOT a skill — an external service
  wrapper with auth + ToS + fragility concerns, and most of its outputs overlap what Violet already
  generates natively (mindmap, report/docx, dashboard). Skip; add native flashcard/quiz skills instead
  if wanted.
- **academic-research-skills** (Imbad0202, **CC-BY-NC 4.0**) — 4 skills: Deep Research, Academic Paper,
  Academic Paper Reviewer (prompt-based, importable), Academic Pipeline (hybrid w/ scripts). Genuinely
  useful for research/academic productivity. The 3 prompt-based ones import via our SKILL.md importer,
  but multi-agent depth flattens to the top SKILL.md, and the **NonCommercial license** constrains use.
  Verdict: useful — import the 3 prompt skills only with the user's OK on the NC license (not auto-copied).

## Status
done (import + assessment). Docker image rebuilt with the imported skills.

## Verification
- Registry loads 12 agents; each imported skill parsed with its full instruction prompt
  (e.g. skill-creator 32.6k chars, internal-comms 1.1k). `get('internal-comms')` resolves.
- Existing suite still green (64 tests; no code changed, only config files added).

## Next
Optional: import the 3 academic prompt-skills (pending NC-license OK); a native "book → skill"
distiller using ingestion + importer; auto-derive triggers for imported skills so they can also
auto-detect (not only explicit-select).
