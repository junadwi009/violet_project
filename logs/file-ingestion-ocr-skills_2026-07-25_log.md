# Phase 3c — Document skills + file ingestion + OCR

- **Date:** 2026-07-25
- **Track:** skills / ingestion / vision
- **Branch:** main
- **Author:** Claude Code

## What
Added 3 document skills, a file-ingestion subsystem (CSV/XLSX/PDF/DOCX → text as a data source),
and image OCR via an OpenRouter vision model. Uploaded files become input for chat and skills.

## New skills (safe artifacts)
- `mindmap` — mind map / flowchart / org chart / process diagram (inline SVG, interactive).
- `minutes` — Minutes of Meeting: structured agenda / decisions / action-items table from notes.
- `documentation` — data dictionary / schema / API / process docs.
Skill library is now 10; detection uses word-boundary + longest-trigger (Phase 3b).

## File ingestion
- Deps added to `pyproject.toml`: `python-multipart`, `pypdf`, `python-docx`, `openpyxl`.
- `ingestion/extractors.py`: `extract_text(filename, data)` for csv/tsv, xlsx, pdf, docx, txt/md/json;
  20k-char cap with a truncation flag; scanned-PDF (no text) → clear error pointing to OCR.
- `ingestion/ocr.py`: `VisionOCR` posts a base64 image to an OpenRouter vision model.
- `routes/upload.py`: `POST /api/upload` (multipart) — images → OCR, documents → extract; size limit.
- `config.py`: `VISION_MODEL` (default `qwen/qwen3-vl-32b-instruct`), `VISION_BASE_URL/API_KEY`
  (defaults to OPENROUTER_API_KEY), `MAX_UPLOAD_MB`. `main.py` builds `VisionOCR` when a key exists.

## OCR model choice
`qwen/qwen3-vl-32b-instruct` via OpenRouter — cheapest capable option ($0.10/M) and strong at OCR /
document understanding; no infra vs self-hosting a HuggingFace model. HF (GOT-OCR2/docTR/PaddleOCR)
noted as alternatives but rejected for lack of hosting.

## Frontend
- `lib/api.ts` `uploadFile` (multipart). Composer gains a paperclip attach button + attachment chip;
  `App` uploads, shows the chip, and injects the extracted text into the next message (display bubble
  stays concise: typed text + 📎 filename; full extracted text is sent to the model).
- Accepts .csv/.tsv/.xlsx/.pdf/.docx/.txt/.md/.json + images (png/jpg/webp/gif/bmp).

## Interfaces / contracts
- New `POST /api/upload`. `Settings` gained vision/upload fields (defaulted). No breaking changes.

## Status
done — tests green, live-verified.

## Verification
- `python -m pytest` → **50 passed** (+7 ingestion: csv/json/docx/xlsx extraction, image/unsupported
  errors, truncation, mime). Frontend `npm run build` clean.
- Live (real key): `/api/skills` → 10. CSV upload → structured extract. **PNG → OCR via qwen3-vl**
  read "INVOICE #2026-07 / Total: Rp 4.250.000 / Vendor Gunung Capital" accurately. End-to-end:
  attached CSV → `table` skill produced an interactive HTML table containing the real data, no
  external refs.
- Docker: image rebuilt with the new deps (see session).

## Next
Scanned-PDF OCR (rasterize pages → vision), CSV/XLSX → chart directly, persisting uploaded docs as a
retrievable source (ties into Track 2 RAG), local vision model option.
