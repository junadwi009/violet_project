import { useEffect, useId, useState } from "react";
import type { PanelProps } from "../SettingsShell";
import { SectionHeader } from "../controls/SectionHeader";
import { SliderRow } from "../controls/SliderRow";
import { TextRow } from "../controls/TextRow";
import { ToggleRow } from "../controls/ToggleRow";
import { canSpeak, listVoices, onVoicesChanged, speakText } from "../../../lib/speech";

const VOICE_KEYS = [
  "voice_lang",
  "voice_name",
  "voice_rate",
  "voice_pitch",
  "auto_speak",
];

export function VoicePanel({
  values,
  overridden,
  patchNow,
  patchDebounced,
  onReset,
}: PanelProps & { onReset: () => void }) {
  // `getVoices()` frequently returns `[]` on first call and fills in later via
  // `voiceschanged` — subscribe rather than read once, and tear the listener
  // down on unmount so re-opening this panel doesn't accumulate them. Lazy
  // initializer so `getVoices()` runs once on mount, not on every render.
  const [voices, setVoices] = useState(() => listVoices());
  useEffect(() => onVoicesChanged(() => setVoices(listVoices())), []);

  const modified = VOICE_KEYS.some((key) => overridden.includes(key));
  const voiceName = String(values.voice_name ?? "");

  const current = {
    lang: String(values.voice_lang ?? "id-ID"),
    voiceName,
    rate: Number(values.voice_rate ?? 1),
    pitch: Number(values.voice_pitch ?? 1),
  };

  // Rate/Pitch/Language render from `SliderRow`/`TextRow`'s own local state
  // and only reach the server (and thus `current` above, which is derived
  // from `values`) after the 300ms debounce settles. Mirror the live value
  // here too, updated in the same `onChange` that feeds `patchDebounced`, so
  // "Test voice" previews what's on screen right now instead of whatever was
  // last persisted. Re-sync whenever the server value changes underneath us
  // (initial load, cross-tab update, group reset).
  const [liveLang, setLiveLang] = useState(current.lang);
  const [liveRate, setLiveRate] = useState(current.rate);
  const [livePitch, setLivePitch] = useState(current.pitch);
  useEffect(() => setLiveLang(current.lang), [current.lang]);
  useEffect(() => setLiveRate(current.rate), [current.rate]);
  useEffect(() => setLivePitch(current.pitch), [current.pitch]);

  // A stored voice name is per-browser/per-OS and may simply not exist here;
  // that's not an error, but the selection silently isn't in effect, so say
  // so. Only judge this once the voice list has actually loaded — `voices`
  // reads `[]` on the first render after every page load in most browsers
  // (Chrome/Safari fill it in asynchronously via `voiceschanged`), and an
  // empty list means "not loaded yet", not "not available".
  const missing =
    voiceName !== "" && voices.length > 0 && !voices.some((v) => v.name === voiceName);

  const selectId = useId();
  const missingId = useId();

  const synthesisUnavailable = !canSpeak();

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Voice"
        description="Uses your browser's built-in speech engine. Available voices differ by browser and operating system."
        modified={modified}
        onReset={onReset}
      />

      {synthesisUnavailable && (
        <p className="text-xs text-steel/70">
          This browser does not support speech synthesis, so the voice,
          rate, pitch, and auto-speak settings below would have no effect.
          Try a Chromium-based browser. Language is still used for speech
          input if this browser supports that.
        </p>
      )}

      {!synthesisUnavailable && (
        <>
          <div>
            <label
              htmlFor={selectId}
              className="block text-xs font-medium text-steel-dark mb-1"
            >
              Voice
            </label>
            {/* Click-driven and rendered straight from `values` — patch
                immediately, same as `ToggleRow` below. See the `patchNow` vs
                `patchDebounced` note on `PanelProps`. */}
            <select
              id={selectId}
              value={voiceName}
              onChange={(event) => patchNow({ voice_name: event.target.value })}
              aria-describedby={missing ? missingId : undefined}
              className="w-full text-xs bg-navy-800 border border-navy-700/20 rounded-lg px-2.5 py-1.5 text-steel-dark focus:outline-none focus:ring-1 focus:ring-steel-highlight/30"
            >
              <option value="">Browser default</option>
              {voices.map((voice) => (
                <option key={voice.name} value={voice.name}>
                  {voice.name} ({voice.lang})
                </option>
              ))}
            </select>
            {missing && (
              <p
                id={missingId}
                className="text-[11px] text-[color:var(--color-warning)] mt-1"
              >
                "{voiceName}" is not available in this browser. The default
                voice is being used instead.
              </p>
            )}
          </div>

          <SliderRow
            label="Rate"
            value={current.rate}
            min={0.5}
            max={2}
            step={0.1}
            onChange={(voice_rate) => {
              setLiveRate(voice_rate);
              patchDebounced({ voice_rate });
            }}
          />
          <SliderRow
            label="Pitch"
            value={current.pitch}
            min={0}
            max={2}
            step={0.1}
            onChange={(voice_pitch) => {
              setLivePitch(voice_pitch);
              patchDebounced({ voice_pitch });
            }}
          />

          <ToggleRow
            label="Speak replies automatically"
            hint="Reads each assistant reply aloud as it arrives."
            on={values.auto_speak === true}
            onToggle={() => patchNow({ auto_speak: !(values.auto_speak === true) })}
          />
        </>
      )}

      {/* Holds its own local state and fires on every keystroke — debounce.
          Kept outside the synthesis gate: it also drives speech *input*
          (`createSpeechRecognizer`'s `lang`), which is a separate capability
          gated by `canRecognizeSpeech()`, not `canSpeak()`. */}
      <TextRow
        label="Language"
        value={String(values.voice_lang ?? "")}
        placeholder="id-ID"
        hint="BCP-47 tag, e.g. id-ID or en-US. Also used for speech input."
        onChange={(voice_lang) => {
          setLiveLang(voice_lang);
          patchDebounced({ voice_lang });
        }}
      />

      {!synthesisUnavailable && (
        <button
          type="button"
          onClick={() =>
            speakText("Halo, saya Violet. Ini contoh suara saya.", {
              lang: liveLang,
              voiceName,
              rate: liveRate,
              pitch: livePitch,
            })
          }
          className="w-full text-xs font-medium text-steel-highlight bg-steel-highlight/10 hover:bg-steel-highlight/15 border border-steel-highlight/30 rounded-lg py-2 transition"
        >
          Test voice
        </button>
      )}
    </div>
  );
}
