# Voice panel and preference-driven speech

- **Date:** 2026-07-28
- **Track:** 5 STT / 6 TTS (cross-cutting: also touches Settings/Task 10 shell)
- **Branch:** feat/settings-overhaul
- **Author:** Claude (Task 14 of the settings-overhaul plan)

## What
Added the Voice settings panel and made `speech.ts` read voice preferences
(`voice_lang`, `voice_name`, `voice_rate`, `voice_pitch`, `auto_speak`,
added server-side in Task 2) instead of hardcoding `id-ID` / rate 1 / pitch 1.
Every existing speech call site (`speakText` in `send()`,
`createSpeechRecognizer` in `handleListen()`, both in `App.tsx`) now passes
the persisted settings through a single `voiceSettingsFromValues()` helper.
`auto_speak` now also triggers speaking a reply, alongside the pre-existing
session-local `speechOutputEnabled` toggle — both routed through one
`speakText` call so enabling both doesn't fire it twice.

## Why
Task 2 added the five voice preference keys server-side but nothing read
them; the Voice tab in `SettingsNav` rendered "Coming in the next task."
This task closes that gap end-to-end: panel UI → PATCH → persisted value →
actually changes what the browser's speech engine does.

## Files touched
- `apps/web-client/src/lib/speech.ts` — shared seam; added `VoiceSettings`,
  `DEFAULT_VOICE`, `listVoices()`, `onVoicesChanged()`; `speakText` and
  `createSpeechRecognizer` now take a `VoiceSettings` param.
- `apps/web-client/src/App.tsx` — added `voiceSettingsFromValues()`; updated
  both call sites; `auto_speak` now gates speaking a reply in `send()`
  alongside `speechOutputEnabled`.
- `apps/web-client/src/components/settings/panels/VoicePanel.tsx` (new) —
  voice select (`patchNow`), language `TextRow` + Rate/Pitch `SliderRow`
  (`patchDebounced`), `auto_speak` `ToggleRow` (`patchNow`), "Test voice"
  button, missing-voice fallback note, `!canSpeak()` fallback state.
- `apps/web-client/src/components/settings/SettingsPanel.tsx` — wired the
  `"voice"` case in `renderPanel()` to `VoicePanel`.
- `apps/web-client/src/components/VoiceOverlay.tsx` — reviewed, no call
  sites of `speakText`/`createSpeechRecognizer` (confirmed via grep); no
  change needed.

## Interfaces / contracts changed
- `speech.ts`: `speakText(text, voice?, onEnd?)` (voice inserted as 2nd
  param — was `speakText(text, onEnd?)`), `createSpeechRecognizer(...,
  voice?)` (voice appended as 4th param). Both default to `DEFAULT_VOICE`
  so any missed call site fails to compile only if it breaks positional
  order, not silently.
- New exports: `VoiceSettings`, `DEFAULT_VOICE`, `listVoices()`,
  `onVoicesChanged()`.

## Status
done

## Verification
- `cd apps/web-client && npm run build` → `tsc -b && vite build` — PASS
  (built in 20.77s, no type errors).
- Browser check (Chromium via preview harness, backend on
  `LLM_PROVIDER=mock`, frontend on 5173 per `vite.config.ts`
  `strictPort: true`):
  - Voice dropdown populated synchronously with 3 Windows SAPI voices
    (`Microsoft David/Mark/Zira`) in this environment — `voiceschanged`
    subscription verified present in code; not forced to prove the async
    fill path since voices were already available on first read here.
  - Selecting a voice fired exactly 1 immediate PATCH
    (`{"voice_name": "..."}"`), confirmed via `GET /api/settings` reading
    back the new value with no debounce delay.
  - Dragging Rate 1.0→2.0 and Pitch 1.0→2.0 (10 synthetic `input` events
    each, simulating a drag) produced 0 PATCH requests synchronously and
    exactly 1 PATCH after the 300 ms debounce window, each with the
    correct final value (`{"voice_rate":2}`, `{"voice_pitch":2}`).
  - Toggling "Speak replies automatically" fired exactly 1 immediate PATCH
    (`{"auto_speak": true}`).
  - Reloaded the page and reopened Settings → Voice: selected voice and
    Rate=2.0 both persisted correctly.
  - Set `voice_name` to a nonexistent value via direct API PATCH, reloaded:
    panel correctly fell back to "Browser default" in the select and
    rendered the "... is not available in this browser" warning.
  - Checked dark mode: `<select>` computes `background: rgb(36,29,49)`
    (`navy-800` dark) / `color: rgb(242,236,250)` — the same high-contrast
    pair `TextRow` documents (~14:1), not the banned `bg-white` /
    `text-steel-dark` combination.
  - "Test voice" and the `auto_speak`-triggered speak after sending a chat
    message were both verified by instrumenting
    `speechSynthesis.speak()` (no way to capture actual audio output in
    this environment) and asserting on the `SpeechSynthesisUtterance`
    passed to it: correct text, `lang="id-ID"`, `rate=2`, `pitch=2`,
    `voice.name="Microsoft Zira - English (United States)"`, and
    `speechSynthesis.speaking === true` immediately after. Did not
    literally listen for audio.
- `data/preferences.json` was PATCHed during testing (voice_name, rate,
  pitch, auto_speak, theme) and restored to `{"ui_mode": "developer"}`
  afterward. Both the backend (`uvicorn`, port 8000) and frontend
  (`vite`, port 5173) test servers were stopped at the end.

## Next
- Task 15+ can build on the same `patchNow`/`patchDebounced` pattern.
- Not covered here: real (non-mock, non-browser-native) TTS/STT providers —
  out of scope per project `CLAUDE.md` (Phase 2 voice = mock scaffolding).
