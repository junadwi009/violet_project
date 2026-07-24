# CLAUDE.md — Project Violet (Violet AI)

> Konteks untuk Claude Code saat kerja di folder ini. Bagian dari workspace `project_dashboard` — lihat `../CLAUDE.md` untuk katalog & aturan umum (jangan commit kredensial).

## Apa ini
Personal AI assistant local-first. Repo mengimplementasi Phase 1 text MVP + scaffolding Phase 2 voice (mock STT/TTS) + placeholder avatar Phase 3. LLM default = mock (tanpa API key). Memory bersifat approval-gated (tidak auto-save).

## Stack
- Python `>=3.11`, FastAPI + uvicorn, Pydantic 2 (editable install `pip install -e ".[dev]"`)
- SQLite lokal (sessions, messages, memories, memory_candidates, gesture_events, tool_audit_logs)
- `apps/web-client`: React + Vite (npm), kontrol speech native browser
- Test: pytest (`.tmp/pytest` basetemp)

## Cara jalan
```bash
# Backend (assistant-core):
uvicorn violet_assistant.main:app --host 127.0.0.1 --port 8000
# Web client:
cd apps/web-client && npm install && npm run dev   # Vite → http://127.0.0.1:5173
# Mock voice services (Phase 2):
uvicorn violet_speech.main:app --host 127.0.0.1 --port 9090   # STT
uvicorn violet_tts.main:app --host 127.0.0.1 --port 8020      # TTS
python -m pytest
```
Endpoint inti: `POST /api/chat`, `GET /health`, `/api/memory/candidates` (+ approve), `/api/personalities`.

## Arsitektur / struktur
Polyrepo / multi-service di satu repo. `services/assistant-core` (`violet_assistant`), `services/speech-service` (`violet_speech`), `services/tts-service` (`violet_tts`) — masing-masing punya `src/` + `tests/` (lihat `pyproject.toml` packages.find). `apps/web-client` React+Vite. `configs/personality/` (profil JSON: `violet.default`, `violet.devoted_strategist`), `configs/avatar/`.

## Env vars (JANGAN tulis nilai asli)
- `LLM_PROVIDER` (default `mock`) / `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` / `LLM_TIMEOUT_SECONDS` — provider OpenAI-compatible (Ollama/LM Studio/vLLM/cloud)
- `STT_*` / `TTS_*` — provider, base url, model/voice, language
- `DATABASE_URL`, `VECTOR_PROVIDER`
- `MEMORY_AUTO_SAVE` / `MEMORY_REQUIRE_APPROVAL` — gating memory
- `ALLOW_SHELL_TOOLS` / `ALLOW_EMAIL_TOOLS` / `ALLOW_FILE_DELETE` / `REQUIRE_CONFIRMATION_FOR_RISKY_TOOLS` — safety toggles
- `VIOLET_API_TOKEN` / `JWT_SECRET`, `APP_*`, `PUBLIC_CLIENT_URL`, `VITE_API_BASE_URL` / `VITE_AVATAR_VRM_PATH`

> `.env.example` aman (hanya nama). `.env` lokal ada di folder — jangan commit secret; pindahkan ke secret manager.

## Dokumen / file yang WAJIB dibaca dulu
- `README.md` — scope per fase, perintah run, safety notes, cara pakai Ollama
- `pyproject.toml` — layout package multi-service + path test
- `docs/` — detail desain per fase
- `docs/06_PARALLEL_DEV_MAP.md` — audit + peta 6 workstream (chat, RAG, vector, avatar 3D, STT, TTS) + batas ownership untuk kerja paralel

## Update Log Rule (WAJIB)
Setiap perubahan (fitur, fix, refactor, wiring, keputusan desain) **wajib** dicatat ke satu file log
di `logs/` dengan format nama: **`{Update}_{Date}_log.md`**
- `{Update}` = slug singkat kebab-case dari perubahan (mis. `rag-retriever`, `tts-xtts`, `avatar-vrm`).
- `{Date}` = tanggal ISO `YYYY-MM-DD` (mis. `2026-07-24`).
- Contoh: `logs/rag-retriever_2026-07-24_log.md`.
- Satu file per update per hari; kalau update yang sama lanjut di hari lain → file baru dengan tanggal baru.
- Pakai `logs/_TEMPLATE.md` sebagai kerangka. Isi minimal: What / Why / Files touched / Track (1–6) / Status / Next.
- Tulis log **di akhir** setiap unit kerja sebelum commit. Jangan commit perubahan tanpa entry log.

## Aturan & gotcha
- LLM mock = DEFAULT: jalan tanpa API key/model server apa pun. Set `LLM_PROVIDER=ollama` + `LLM_BASE_URL` untuk pakai endpoint OpenAI-compatible.
- Memory tidak auto-save: pernyataan jadi candidate, harus di-approve dulu (`MEMORY_REQUIRE_APPROVAL`).
- Risky tools (shell/email/file-delete) tidak diimplementasi di Phase 1 dan gated oleh env flags.
- Avatar Phase 3 hanya placeholder; butuh asset manual `apps/web-client/public/avatar/violet.vrm` (jangan commit asset berlisensi).

## Status
Phase 1 text MVP jalan; Phase 2 voice = mock scaffolding; Phase 3 avatar = placeholder. Out of scope: real voice cloning, STT/TTS model nyata, VRM rendering, autonomous tools, VPS deploy.
