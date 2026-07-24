# Phase 3d — Report / document / PPTX generation (downloadable files)

- **Date:** 2026-07-25
- **Track:** skills / document generation
- **Branch:** main
- **Author:** Claude Code

## What
Added downloadable Office-file generation: **report/document → .docx** and **presentation → .pptx**.
Skill library is now 12.

## Architecture (safe)
The LLM emits a structured JSON spec (never code, never a binary); the backend deterministically
renders the real file with python-docx / python-pptx and returns it base64-encoded in the artifact.
No code execution. Same spec→render pattern as chart specs.

## Backend
- `documents/render.py`: `render_docx(spec)` (title/subtitle/sections with paragraphs/bullets/table)
  and `render_pptx(spec)` (title + slides with bullets/notes). Tolerant of sparse specs.
- `skills/generator.py`: `parse_artifacts` now also recognizes ```docx / ```pptx JSON blocks;
  `_render_file_artifacts` renders them to bytes → base64 + filename (slug of title) + mime, and
  clears the spec. Failed renders are dropped.
- `schemas/chat.py` `Artifact`: added `file_base64`, `filename`, `mime` for downloadable kinds.
- `configs/skills/presentation.json` (kind pptx) and `report.json` (kind docx) — with strict-JSON
  spec schemas in the prompts.
- `pyproject.toml`: added `python-pptx` (python-docx already present).

## Frontend
- `lib/api.ts` `Artifact` gained the file fields. `ArtifactView` renders a **download card** for
  docx/pptx (icon + filename + Download button that decodes base64 → Blob → downloads).

## Interfaces / contracts
- `Artifact` gained file fields (additive). New skills only. No breaking changes.

## Status
done — tests green, live-verified.

## Verification
- `python -m pytest` → **55 passed** (+5: docx/pptx render valid OOXML zips, sparse specs,
  parse+render for both). Frontend `npm run build` clean.
- Live (real key): `/api/skills` → 12. PPTX request → valid 33 KB .pptx, opened with **6 slides**
  (title + Pendahuluan…Kesimpulan). DOCX request → valid 37 KB .docx, opened with **10 paragraphs +
  1 table** (Executive Summary → Rekomendasi). Filenames derived from the title.
- Docker: image rebuilt with python-pptx (see session).

## Next
PDF export (report → PDF), charts/images embedded inside docx/pptx, templated brand themes,
persisting generated files.
