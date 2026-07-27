# Design — Settings Overhaul

Date: 2026-07-27
Status: Approved (brainstorming → spec). Implementation plan not yet written.
Scope: `project_violet` (assistant-core backend + web-client frontend)
Depends on: `PreferencesStore` / `/api/settings` (2026-07-25), `SQLiteStore`,
`FileMemoryStore`, knowledge base, skills, agents.

## Summary

`SettingsModal.tsx` is a single 500-line component holding ten unrelated
concerns in one narrow scrolling column. It cannot absorb another group, and
several of the groups it already has are broken: persona and provider selections
do not survive a reload, the `overridden` / `defaults` data the API returns is
fetched and thrown away, and the temperature slider issues one HTTP request and
one file write per 0.1 step of drag.

This design does two things at once, because doing either alone would mean
touching the same file twice:

1. **Restructure** — the modal becomes a wide shell with a left nav rail and one
   small panel component per group.
2. **Extend** — four new groups (Appearance, Model & routing, Voice, Data &
   privacy) and the fourteen preference keys they need.

The behavioral fixes ride along with the restructure.

### Decisions taken during brainstorming

| Question | Decision |
|---|---|
| Layout | Modal + left sidebar tabs (not full-page route, not accordion) |
| Client-only prefs (theme, density, voice) | Server-owned, with a localStorage cache used only to avoid first-paint flash |
| Data & privacy scope | Read-only safety panel + clear sessions + export |
| Search across settings | **Cut.** Nine groups do not justify a keyword index |

### Non-goals

- Wiring `speech-service` / `tts-service` to the web client. Voice settings
  configure the browser's Web Speech API, which is what the client actually uses
  today ([`lib/speech.ts`](../../../apps/web-client/src/lib/speech.ts)).
- Making API keys, base URLs, or `ALLOW_*` safety flags editable. They stay
  frozen in `.env`. See **Security boundary**.
- Wiping memories. Rejected during brainstorming; per-memory delete already
  exists and stays the only path.
- Adding a frontend test runner. The web client has none; verification is
  `tsc -b` plus driving the real UI.

---

## Part 1 — Preferences store gains structure

### The problem with the current shape

```python
EDITABLE_KEYS: dict[str, Callable[[Any], bool]] = {
    "temperature": _num(0.0, 2.0),
    ...
}
```

A bare validator carries no metadata. The server cannot answer "which keys
belong to Appearance?", so the client cannot offer "reset this section", and the
`overridden` list the API already returns has nowhere useful to render.

### New shape

```python
@dataclass(frozen=True)
class PrefSpec:
    validate: Callable[[Any], bool]
    group: str


EDITABLE_KEYS: dict[str, PrefSpec] = {
    "ui_mode":     PrefSpec(_choice("user", "developer"), "general"),
    "theme":       PrefSpec(_choice("light", "dark", "system"), "appearance"),
    "temperature": PrefSpec(_num(0.0, 2.0), "model"),
    ...
}
```

Validation behavior is unchanged — `patch()` still rejects unknown keys with
`ValueError` and the route still maps that to 422. The only addition is `group`.

### Full key table

Existing keys keep their names and defaults; the `Group` column is new.

| Key | Type / range | Default source | Group |
|---|---|---|---|
| `ui_mode` | `user` \| `developer` | `"user"` | general |
| `default_personality` | str ≤200 | `"violet.default"` | general |
| `default_provider` | str ≤200 | `settings.llm_provider` | general |
| `theme` | `light` \| `dark` \| `system` | `"system"` | appearance |
| `ui_density` | `cozy` \| `compact` | `"cozy"` | appearance |
| `font_scale` | 0.875–1.25 | `1.0` | appearance |
| `accent` | `violet` \| `indigo` \| `teal` \| `amber` \| `rose` | `"violet"` | appearance |
| `llm_model` | str ≤200 | `settings.llm_model` | model |
| `temperature` | 0.0–2.0 | `settings.default_temperature` | model |
| `persona_model` | str ≤200 | `settings.persona_model` | model |
| `technical_model` | str ≤200 | `settings.technical_model` | model |
| `artifact_model` | str ≤200 | `settings.artifact_model` | model |
| `vision_model` | str ≤200 | `settings.vision_model` | model |
| `agent_default_model` | str ≤200 | `settings.agent_default_model` | model |
| `web_search_model` | str ≤200 | `settings.web_search_model` | model |
| `web_search_enabled` | bool | `False` | behavior |
| `canvas_enabled` | bool | `True` | behavior |
| `memory_require_approval` | bool | `settings.memory_require_approval` | behavior |
| `memory_auto_save` | bool | `settings.memory_auto_save` | behavior |
| `voice_lang` | str ≤200 (BCP-47) | `"id-ID"` | voice |
| `voice_name` | str ≤200 (`""` = browser default) | `""` | voice |
| `voice_rate` | 0.5–2.0 | `1.0` | voice |
| `voice_pitch` | 0.0–2.0 | `1.0` | voice |
| `auto_speak` | bool | `False` | voice |
| `knowledge_auto_sync` | bool | `settings.knowledge_auto_sync` | knowledge |

Twenty-five keys, fourteen of them new. `accent` is an enum of token-set names,
not a free-form color — a free hex would let a bad value produce unreadable
contrast, and each accent needs a matched set of tokens per theme anyway (see
Part 4).

`llm_provider` appears both as the default source for `default_provider` and in
the read-only `locked` block. These are different things and both are wanted:
`locked.llm_provider` reports which provider the deployment is configured with,
while `default_provider` is the user's override of which provider the UI sends
with. The locked value is what the override falls back to when cleared.

**`voice_name` caveat:** browser voice lists are per-browser and per-OS. A stored
name that the current browser does not offer falls back to the default voice
silently rather than erroring; the Voice panel shows a note when the stored name
is unavailable.

### Model keys are not secrets

`persona_model` and friends are identifiers like `nousresearch/hermes-4-70b`.
The corresponding `*_base_url` and `*_api_key` fields stay in frozen `Settings`
and are never exposed. This preserves the rule written at
[`store.py:9`](../../../services/assistant-core/src/violet_assistant/preferences/store.py).

**Consumer wiring:** each `*_model` key is read through
`PreferencesStore.effective()` at the point of use, the same way `temperature`
already is. Any call site that currently reads `settings.persona_model`
directly must switch to the effective value, or the setting will appear to save
but change nothing. The implementation plan enumerates these call sites; a test
asserts an overridden `persona_model` reaches the layer that builds the request.

---

## Part 2 — New endpoints

### `POST /api/settings/reset`

```
Request:  {"group": "appearance"}   or   {"keys": ["temperature", "llm_model"]}
Response: {values, defaults, overridden, locked}   (same payload as GET)
```

Exactly one of `group` / `keys` must be present — 422 otherwise. An unknown
group or key is a 422, not a silent no-op. Resetting deletes those entries from
`data/preferences.json`, so `effective()` falls back to the `Settings` default.

This is what makes `overridden` load-bearing: `SectionHeader` shows a modified
dot when any key in its group appears in `overridden`, and enables the reset
button only then.

### `GET /api/settings` gains a `locked` block

```json
"locked": {
  "llm_provider": "mock",
  "agent_tools_enabled": false,
  "allow_shell_tools": false,
  "allow_email_tools": false,
  "allow_file_delete": false,
  "require_confirmation_for_risky_tools": true,
  "tool_confirm_threshold": "high",
  "max_tool_iterations": 5
}
```

Read-only. Built from an explicit **allowlist of key names** — never by
iterating `Settings` and filtering, because a filter silently starts leaking the
moment someone adds a field whose name the filter did not anticipate. A test
asserts the block contains only the eight names above.

### `DELETE /api/sessions/{session_id}` and `DELETE /api/sessions`

```
Response: {"deleted_sessions": 1, "deleted_messages": 14, "deleted_candidates": 2}
```

404 if `session_id` does not exist. `DELETE /api/sessions` with no id clears all.

**Cascade must be explicit.** The schema declares
`FOREIGN KEY (session_id) REFERENCES sessions(id)` without `ON DELETE CASCADE`,
and SQLite does not enforce foreign keys at all unless `PRAGMA foreign_keys=ON`.
So `SQLiteStore.delete_session()` deletes, in one transaction:

1. `memory_candidates` whose `source_message_id` is in the session's messages —
   otherwise pending candidates linger in the approval drawer pointing at
   messages that no longer exist,
2. the session's `messages`,
3. the `sessions` row.

`memories` are **not** touched — an approved memory has been promoted out of the
conversation that produced it and outlives it. `tool_audit_logs` are not touched
either; they are an audit trail and deleting a chat must not erase it.

### `GET /api/export`

Returns a single JSON bundle with `Content-Disposition: attachment`:

```json
{
  "exported_at": "2026-07-27T09:00:00Z",
  "schema_version": 1,
  "sessions": [{...}],
  "messages": [{...}],
  "memories": [{...}],
  "preferences": {"values": {...}, "overridden": [...]}
}
```

`locked` is deliberately **excluded** — the export is a user-data backup, not a
config dump, and it should not carry a snapshot of the deployment's safety
posture into a file that gets emailed around.

Export is read-only and import is out of scope. It exists so that "clear
sessions" has a backup path.

---

## Part 3 — Frontend structure

### From one file to a directory

```
components/settings/
  SettingsModal.tsx        shell: overlay, focus trap, Esc, nav, panel switch, error line
  SettingsNav.tsx          left rail; groups + "dev" divider
  useDebouncedPatch.ts     local-state-now, PATCH-after-idle
  controls/
    ToggleRow.tsx          (moved from SettingsModal, unchanged behavior)
    SegmentedRow.tsx       ( Light | Dark | System )
    SliderRow.tsx          debounced numeric
    TextRow.tsx            debounced string, for model ids
    SectionHeader.tsx      title + modified dot + "Reset section"
  panels/
    GeneralPanel.tsx       ui_mode, persona, session summary
    AppearancePanel.tsx    theme, density, font scale, accent
    ModelPanel.tsx         provider, cascade layer models, temperature, web-search model
    BehaviorPanel.tsx      web search, canvas, memory approval / auto-save
    VoicePanel.tsx         lang, voice, rate, pitch, auto-speak, Test voice
    KnowledgePanel.tsx     extracted from current modal, unchanged behavior
    SkillsPanel.tsx        extracted; skill list + Skill Lab entry
    AgentsPanel.tsx        extracted; delegation picker
    DataPanel.tsx          locked safety panel, export, clear sessions
```

Each panel receives only the props it needs and can be read end to end. The
shell knows nothing about any panel's contents beyond its id, label, icon, and
whether it is dev-only.

### Panel contract

```ts
type PanelProps = {
  values: SettingsValues;
  overridden: string[];
  patch: (changes: Record<string, string | number | boolean>) => void;
  devMode: boolean;
};
```

Panels that need more (Knowledge needs reindex and Drive callbacks, Skills needs
`onOpenSkillLab`, Agents needs the agent list) extend this with their own extra
props. The point is that the shell does not grow a union of every panel's needs
— it passes the common four and spreads a per-panel extras object.

### Group visibility

`ui_mode` already gates dev-only controls. Under the new nav that becomes coarse
and fine: Model and Agents are dev-only **groups** (hidden from the rail in user
mode), while individual dev-only **rows** inside shared panels keep their
existing `devMode &&` guards. In user mode the rail shows General, Appearance,
Behavior, Voice, Knowledge, Skills, Data.

The approved mockup showed a single "Advanced" entry below a `── dev ──`
divider. That divider is kept, but what sits below it is the real dev-only
groups — Model and Agents — rather than one catch-all panel. A group named
"Advanced" would be a bucket with no defining purpose, which is the shape the
current modal already failed at.

### Debounced writes

```ts
const patch = useDebouncedPatch(onPatchSettings, 300);
```

Slider and text controls hold their own local value so the UI stays responsive,
and flush a single PATCH 300ms after the last change. Toggles and segmented
controls patch immediately — they are discrete and one write per click is
correct. A pending flush is forced on modal close so a value typed and
immediately dismissed is not lost.

This replaces the current `onChange={(e) => onPatchSettings(...)}` on the
temperature range input, which writes `data/preferences.json` on every step.

### Accessibility

The current modal can only be dismissed by clicking the backdrop. Adds:
`role="dialog"` + `aria-modal="true"` + `aria-labelledby`, Escape to close,
focus trap within the modal, focus returned to the trigger on close, and the nav
rail as `role="tablist"` with arrow-key navigation between tabs.

### Error feedback

`handlePatchSettings` currently routes failures to the app-level status bar,
which renders behind the modal overlay — a rejected patch is invisible. The
modal takes its own error state and renders it in the panel header region.

---

## Part 4 — Theming

### Token overrides

[`index.css`](../../../apps/web-client/src/index.css) already declares every
color as a `@theme` token with the comment "Colors are tokens so a dark variant
can be added later." Collecting on that:

```css
[data-theme="dark"] {
  --color-navy-950: #14101c;
  --color-navy-900: #1c1626;
  --color-navy-800: #241d31;
  --color-navy-700: #3a2f4d;
  --color-steel: #b9a9d1;
  --color-steel-light: #8d7da8;
  --color-steel-ice: #241d31;
  --color-steel-dark: #f2ecfa;
  --color-steel-highlight: #a855f7;
}
```

Note `--color-steel-dark` inverts from near-black to near-white: it is the
primary ink token, and its name describes its light-mode value, not its role.
Renaming tokens is out of scope; the implementation plan calls this out so the
inversion is not mistaken for a bug.

### Accent

`--color-steel-highlight` is the only accent-carrying token, so an accent is one
value per theme — a light-mode hue and a darker-background-safe variant:

```css
[data-accent="teal"]                    { --color-steel-highlight: #0d9488; }
[data-theme="dark"][data-accent="teal"] { --color-steel-highlight: #2dd4bf; }
```

Five accents (`violet`, `indigo`, `teal`, `amber`, `rose`) × two themes = ten
declarations, with `violet` matching today's `#7b2cbf` / `#a855f7` so the
default is unchanged. Every accent value is checked to hold ≥4.5:1 against its
theme's surface token, since the accent is used for text and not only for fills.

### Density and font scale

Both are deliberately narrow. `font_scale` multiplies the root font size, which
scales every `rem`-based Tailwind utility at once:

```css
html { font-size: calc(16px * var(--font-scale, 1)); }
```

`ui_density` adjusts vertical rhythm only — a `--row-pad` token consumed by chat
message rows, sidebar session rows, and settings rows (`0.75rem` cozy,
`0.5rem` compact). It does not touch horizontal padding, font sizes, or the
avatar and composer, because a density switch that reflows everything is a
second theme in disguise and a much larger visual-regression surface.

### Hardcoded values must be swept

Token overrides only reach utilities that go through tokens. Two categories
bypass them and must be converted before dark mode is correct:

- Arbitrary hex utilities — e.g. `bg-[#9d4edd]` in the current palette preview.
- Raw Tailwind palette colors used semantically — `text-emerald-600` for
  "connected", `text-amber-600` for warnings. These get new `--color-success` /
  `--color-warning` tokens with per-theme values.

The implementation plan includes a grep sweep across `src/components/` as an
explicit step, not an afterthought.

### First-paint flash

Server is the source of truth, but `/api/settings` resolves after React mounts,
so a dark-theme user would see a flash of light on every load. `lib/theme.ts`:

```ts
applyAppearance(prefs)        // stamps data-theme / data-density / --font-scale on <html>
readCachedAppearance()        // localStorage
writeCachedAppearance(prefs)  // called after every successful appearance patch
```

A small inline script in `index.html` reads the cache and stamps `<html>` before
the bundle loads. When `/api/settings` arrives, the server value is applied and
the cache rewritten — server always wins, the cache is only a paint hint. A
stale cache costs one frame of the wrong theme, never a wrong saved value.

`theme: "system"` follows `prefers-color-scheme` via a media query listener, so
it tracks OS changes while the app is open.

---

## Part 5 — Behavioral fixes folded in

### Persona / provider / agent persistence

Today [`App.tsx`](../../../apps/web-client/src/App.tsx) initializes
`personalityId` to a hardcoded `"violet.default"` and overwrites
`selectedProvider` with the server's active provider on every load, so both
selections reset on reload despite `default_personality` and `default_provider`
existing as editable keys.

After: selecting a persona or provider patches the corresponding key, and App
initializes from `settings.values` once settings resolve, falling back to the
current defaults when a stored id no longer exists (a personality removed from
`configs/personality/` must not leave the app pointing at a missing profile).

`selectedAgent` stays session-local and is deliberately not persisted — agent
delegation is a per-task choice, and silently resuming a delegation days later
would be surprising.

### Voice reads preferences

`speech.ts` hardcodes `lang = "id-ID"`, `rate = 1`, `pitch = 1` in both
`createSpeechRecognizer` and `speakText`. Both take a settings argument instead.
`auto_speak` decides whether the client speaks assistant replies without being
asked. The Voice panel gets a "Test voice" button that speaks a fixed sample
with the current settings, so the knobs are verifiable without sending a message.

### Destructive action gating

"Clear all sessions" requires typing the word `delete` into a confirmation
field. A single click is not enough for an irreversible action, and a plain
`confirm()` dialog is dismissed reflexively. The Data panel places the Export
button above the clear controls so the backup path is encountered first.

---

## Security boundary

Restated because this design adds settings surface, which is exactly when a
boundary erodes:

| Category | Where it lives | Editable in UI |
|---|---|---|
| API keys (`*_api_key`) | frozen `Settings` / `.env` | never |
| Base URLs (`*_base_url`) | frozen `Settings` / `.env` | never |
| DB / filesystem paths | frozen `Settings` / `.env` | never |
| `ALLOW_SHELL_TOOLS`, `ALLOW_EMAIL_TOOLS`, `ALLOW_FILE_DELETE` | frozen `Settings` / `.env` | never — **shown read-only** |
| `REQUIRE_CONFIRMATION_FOR_RISKY_TOOLS`, `tool_confirm_threshold` | frozen `Settings` / `.env` | never — **shown read-only** |
| Model identifiers | `PreferencesStore` | yes |
| UX / behavior toggles | `PreferencesStore` | yes |

Displaying a safety flag is not the same as being able to change it. The whole
point of the read-only panel is that you can see the posture without a path to
weaken it from the browser. Per `docs/03_SECURITY_RULES.md` rule #5, risky-tool
confirmation is not something a UI toggle may disable.

---

## Testing

### Backend (`pytest`)

- Each new key: valid value accepted, out-of-range and wrong-type rejected with
  422, unknown key still rejected.
- `POST /api/settings/reset` by group clears only that group's overrides.
- `POST /api/settings/reset` by keys clears exactly those keys.
- Reset with neither / both of `group` and `keys` → 422; unknown group → 422.
- `locked` block contains exactly the eight allowlisted names — asserted against
  a literal set, so adding a `Settings` field cannot silently widen it.
- `delete_session` removes messages and orphan-able candidates, leaves memories
  and `tool_audit_logs` intact; unknown id → 404.
- `DELETE /api/sessions` clears all sessions and their messages.
- `GET /api/export` includes sessions, messages, memories, preferences, and does
  **not** include `locked` or any key matching `api_key|base_url|token|secret`.
- An overridden `persona_model` reaches the layer that builds the LLM request.

### Frontend

No test runner exists, so verification is `npm run build` (`tsc -b` strict, then
Vite) plus driving the running app in the browser:

- Toggle Appearance → Dark; confirm surfaces, text, and borders all invert and
  no element keeps a light-mode hardcoded color.
- Reload with dark active; confirm no light flash before mount.
- Drag the temperature slider across its range; confirm exactly one PATCH lands
  in the network log.
- Change persona, reload, confirm it is still selected.
- Open with keyboard only: Tab into the modal, arrow through the nav rail, Esc
  to close, confirm focus returns to the settings trigger.
- Trigger a rejected patch and confirm the error renders inside the modal.

---

## Risks

| Risk | Mitigation |
|---|---|
| Dark mode looks broken because a hardcoded color was missed | Explicit grep sweep step in the plan; visual check of every panel and the main chat surface, not just the modal |
| `*_model` override saves but has no effect because a call site still reads `Settings` directly | Test asserting the effective value reaches the request builder; plan enumerates call sites |
| Nine-way panel split churns a lot of code at once | Panels are extracted with behavior unchanged first, new groups added second — so a regression is bisectable to one of two commits |
| Clear-sessions used without exporting | Export button placed above the destructive controls; typed confirmation |
| Stale localStorage appearance cache | Cache is a paint hint only; server value always overwrites on arrival |

## Out of scope / follow-ups

- Import (the inverse of `/api/export`).
- Per-personality preference overrides.
- Wiring `speech-service` / `tts-service` into the client, which would turn the
  Voice panel's browser knobs into a provider choice.
- Settings search, if the group count grows past what a rail comfortably holds.
