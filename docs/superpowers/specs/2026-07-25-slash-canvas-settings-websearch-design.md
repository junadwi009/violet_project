# Design — Slash Skills · Runtime Settings · Canvas · Web Search

Date: 2026-07-25
Status: Approved (brainstorming → plan)
Scope: `project_violet` (assistant-core backend + web-client frontend)

## Summary

Four related capabilities added to Violet, all sharing the theme "let the user
explicitly invoke and configure Violet's capabilities":

1. **Slash-command skills** — type `/` to explicitly pick a skill (instead of
   relying only on keyword auto-detection).
2. **Runtime-editable preferences** — a "Claude-like" settings surface for
   behavior/UX preferences, persisted and merged over env defaults.
3. **Canvas mode** — a dedicated resizable side panel for artifacts (like Claude
   Artifacts / Gemini Canvas), replacing inline-only rendering.
4. **Web search / crawl** — outbound web capability via OpenRouter `:online`
   plus a lightweight direct-URL fetch/extract tool.

### Guiding principle (security boundary)

Secrets and infrastructure (API keys, base URLs, DB paths, safety toggles that
gate shell/email/file-delete) **stay in `.env` and the frozen `Settings`
dataclass**. Only behavior/UX preferences become runtime-editable. This keeps
the existing privacy posture (local-first, sandboxed HTML artifacts with
`connect-src 'none'`) intact.

---

## Feature 1 — Slash-command skills

### Backend
- `ChatRequest` (schemas/chat.py) gains `skill_id: str | None = None`,
  mirroring the existing `agent` field.
- `SkillRegistry` gains `get(skill_id: str) -> Skill | None`.
- `ChatOrchestrator.chat` precedence becomes:
  `mock → explicit agent → web-search → **explicit skill** → auto-detected skill
  → auto-detected agent → cascade → provider`.
  An explicit skill runs `skill_engine.generate(skill, content)` directly,
  bypassing keyword matching. If `skill_engine` is unavailable (no artifact key),
  fall through to normal handling and surface a note in the intro text.

### Frontend
- `Composer`: when the trimmed draft starts with `/`, render a floating
  **skill palette** filtered as the user types (populated from `fetchSkills()`).
  - Selecting a skill sets a removable **skill chip** and clears the `/…` text.
  - `Enter`/click on a palette item selects; `Esc` closes the palette.
  - Keyboard up/down navigation is a nice-to-have, not required for v1.
- A `skill` (id) prop threads from `App` → `Composer`; the active chip id is
  passed to `sendChat`.
- `sendChat()` in `lib/api.ts` gains an optional `skillId` argument →
  `skill_id` in the POST body.
- The chip persists until the message is sent or the user removes it (one-shot
  per message, matching how `agent` behaves conceptually but chosen per-send).

### Data / API
- No new endpoint; reuse `GET /api/skills`.

---

## Feature 2 — Runtime-editable preferences

### New module: `PreferencesStore`
- Location: `services/assistant-core/src/violet_assistant/preferences/store.py`.
- Persistence: JSON file at `data/preferences.json` (repo `data/` dir, already
  used by `violet.db`). Created on first write; absent file = all defaults.
- Pure, testable: load → dict, patch → validate → write. No network.

### Editable keys (NO secrets)
| Key | Type | Default source |
|---|---|---|
| `llm_model` | str | `Settings.llm_model` |
| `temperature` | float (0.0–2.0) | `0.2` (new constant) |
| `memory_require_approval` | bool | `Settings.memory_require_approval` |
| `memory_auto_save` | bool | `Settings.memory_auto_save` |
| `web_search_enabled` | bool | `false` |
| `web_search_model` | str | `Settings.web_search_model` |
| `canvas_enabled` | bool | `true` |
| `default_personality` | str | `violet.default` |
| `default_provider` | str | `Settings.llm_provider` |

Unknown keys in a PATCH are rejected (422). Range/type validated via a Pydantic
model `PreferencesPatch`.

### Effective settings
- A small helper `effective_preferences(settings, store)` returns a dict of the
  merged values (override if present else default). The orchestrator and routes
  read from it per request rather than from the frozen `Settings` for these keys.
- Temperature/model flow into `LLMOptions`; memory flags into the memory
  candidate flow; web_search/canvas flags gate features.

### API
- `GET /api/settings` → `{ values: {...effective}, defaults: {...}, overridden: [keys] }`.
- `PATCH /api/settings` → body is a partial of editable keys; persists overrides;
  returns the same shape as GET.

### Frontend
- `SettingsModal` gains:
  - **Skills list** section (the "skill dictionary"): every skill's name /
    description / kind, with a button to open Skill Lab. Read-only list.
  - **Behavior** controls: temperature slider, model text field, memory-approval
    toggle, auto-save toggle, web-search toggle + model field, canvas toggle.
  - Controls call `fetchSettings()` / `patchSettings()` (new in `lib/api.ts`).
- `App` loads settings on mount; changes apply to subsequent sends.

---

## Feature 3 — Canvas side panel

Frontend-only; artifacts already arrive from the backend unchanged.

### Components
- New `CanvasPanel` component:
  - Resizable right-hand panel (drag handle; min/max width; remembers width in
    `localStorage`).
  - Renders the **open artifact** large by reusing the existing `Chart / Html /
    File` renderers extracted from `ArtifactView` (refactor those three into
    exported sub-renderers so both inline card and canvas share them).
  - Header: title, kind badge, expand-to-fullscreen, download / copy-HTML,
    close.
  - **Gallery strip**: thumbnails/list of every artifact in the current session;
    click to switch the open artifact.
- `ArtifactView` (inline) becomes a compact **card** with an "Open in canvas"
  action instead of rendering full-size inline. When `canvas_enabled` is false,
  it renders inline exactly as today (backward compatible).

### App wiring
- `App` state: `canvasOpen: boolean`, `canvasArtifactId: string | null`, and a
  derived `sessionArtifacts` list gathered from all assistant messages.
- Layout: main chat is `flex-1`; when canvas is open on desktop, chat and canvas
  split horizontally. On viewports below `lg`, canvas is a full-screen overlay.
- Opening any artifact sets `canvasOpen = true` and the target id.

---

## Feature 4 — Web search / crawl

### Config (Settings + env, secrets stay in env)
- `web_search_base_url` (default `OPENROUTER_BASE_URL`).
- `web_search_model` (default reuses an OpenRouter model, e.g. `technical_model`).
- Key: reuse `OPENROUTER_API_KEY` (no new secret).
- Feature availability = key present AND `web_search_enabled` preference true.

### Online chat (search + read)
- A web-enabled call uses the existing `OpenAICompatibleProvider` pointed at
  OpenRouter, with the model set to `f"{web_search_model}:online"`. OpenRouter
  performs the search, reads results, and returns cited text.
- `ChatRequest` gains `web_search: bool = False`.
- Orchestrator: when `web_search` is true and the web provider is configured,
  route the message through the online provider (precedence just after explicit
  agent). Response text is returned as-is; citation URLs (from OpenRouter
  annotations when available) are appended/returned in `ChatResponse`.
- If web mode is requested but unavailable, return a clear message rather than
  silently falling back.

### Direct URL fetch/crawl tool
- New endpoint `POST /api/fetch` `{ url }` → `{ url, title, text, chars,
  truncated }`.
- Implementation: `httpx` GET with a timeout and size cap, HTML → readable text
  (strip scripts/styles; a minimal extractor, no heavy deps). Only `http(s)`
  URLs; block obviously-internal hosts (localhost/127.0.0.1/private ranges) to
  avoid SSRF against the local machine.
- Exposed in the UI as part of the web toggle affordance (paste a URL → fetch),
  and usable as `/web` context.

### Frontend
- **Globe toggle** in `Composer`; `/web` slash alias selects it. When active,
  `sendChat` sends `web_search: true`.
- Citations render as a small source list under the assistant answer.
- Toggle hidden/disabled when the feature is unavailable.

---

## Error handling
- Explicit skill id not found → 200 with a normal LLM answer + intro note
  ("Skill X not found, answering normally"). Never 500 on a bad skill id.
- `PATCH /api/settings` invalid value → 422 with field detail; store unchanged.
- `/api/fetch` on blocked/invalid/oversized URL → 400 with reason.
- Web search unavailable → answer explains the feature is off / unconfigured.
- Canvas: an artifact that fails to render shows the existing per-renderer error
  state inside the panel.

## Testing
- `PreferencesStore`: load-default, patch-merge-persist, reject-unknown-key,
  range validation (pure unit tests).
- Orchestrator: explicit skill routing; web_search routing with a fake provider;
  precedence ordering unchanged for existing paths.
- `parse_artifacts` unchanged (already covered).
- `/api/fetch`: host-blocking (SSRF) and HTML→text extraction (pure, mocked
  transport).
- Settings/skills routes: shape of GET/PATCH.
- Frontend: no framework test harness exists today → verify via `npm run build`
  (typecheck) and manual smoke; keep components small and typed.

## Build order
1. `PreferencesStore` + `/api/settings` (+ new `Settings` fields, `temperature`
   default, `web_search_*`). Foundation for canvas/web toggles.
2. Backend chat: `skill_id`, `web_search` routing; `SkillRegistry.get`.
3. `/api/fetch` URL tool with SSRF guard.
4. Frontend: `lib/api.ts` additions; slash palette + skill chip in `Composer`.
5. Frontend: extract shared artifact renderers; `CanvasPanel`; App wiring.
6. Frontend: expanded `SettingsModal` (skills list + preference controls).
7. Frontend: web globe toggle + citations.

Each unit: tests where applicable + a `logs/{update}_{date}_log.md` entry before
commit, per the repo rule.

## Out of scope
- Making secrets/infra runtime-editable.
- Multi-user / auth for the settings API (local-first, single user).
- Streaming responses; persisting canvas artifacts across restarts (artifacts
  remain per-session in-memory as today).
- Full readability/boilerplate-removal parity with a library like Readability;
  the fetch extractor is intentionally minimal.
