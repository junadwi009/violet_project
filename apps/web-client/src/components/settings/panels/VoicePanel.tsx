import { useEffect, useState } from "react";
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
  // down on unmount so re-opening this panel doesn't accumulate them.
  const [voices, setVoices] = useState(listVoices());
  useEffect(() => onVoicesChanged(() => setVoices(listVoices())), []);

  const modified = VOICE_KEYS.some((key) => overridden.includes(key));
  const voiceName = String(values.voice_name ?? "");
  // A stored voice name is per-browser/per-OS and may simply not exist here;
  // that's not an error, but the selection silently isn't in effect, so say so.
  const missing = voiceName !== "" && !voices.some((v) => v.name === voiceName);

  const current = {
    lang: String(values.voice_lang ?? "id-ID"),
    voiceName,
    rate: Number(values.voice_rate ?? 1),
    pitch: Number(values.voice_pitch ?? 1),
  };

  if (!canSpeak()) {
    return (
      <div className="space-y-5">
        <SectionHeader title="Voice" modified={false} />
        <p className="text-xs text-steel/70">
          This browser does not support speech synthesis, so voice settings
          would have no effect. Try a Chromium-based browser.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Voice"
        description="Uses your browser's built-in speech engine. Available voices differ by browser and operating system."
        modified={modified}
        onReset={onReset}
      />

      <div>
        <label className="block text-xs font-medium text-steel-dark mb-1">
          Voice
        </label>
        {/* Click-driven and rendered straight from `values` — patch
            immediately, same as `ToggleRow` below. See the `patchNow` vs
            `patchDebounced` note on `PanelProps`. */}
        <select
          value={voiceName}
          onChange={(event) => patchNow({ voice_name: event.target.value })}
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
          <p className="text-[11px] text-[color:var(--color-warning)] mt-1">
            "{voiceName}" is not available in this browser. The default voice
            is being used instead.
          </p>
        )}
      </div>

      {/* Holds its own local state and fires on every keystroke — debounce. */}
      <TextRow
        label="Language"
        value={String(values.voice_lang ?? "")}
        placeholder="id-ID"
        hint="BCP-47 tag, e.g. id-ID or en-US. Also used for speech input."
        onChange={(voice_lang) => patchDebounced({ voice_lang })}
      />

      <SliderRow
        label="Rate"
        value={current.rate}
        min={0.5}
        max={2}
        step={0.1}
        onChange={(voice_rate) => patchDebounced({ voice_rate })}
      />
      <SliderRow
        label="Pitch"
        value={current.pitch}
        min={0}
        max={2}
        step={0.1}
        onChange={(voice_pitch) => patchDebounced({ voice_pitch })}
      />

      <ToggleRow
        label="Speak replies automatically"
        hint="Reads each assistant reply aloud as it arrives."
        on={values.auto_speak === true}
        onToggle={() => patchNow({ auto_speak: !(values.auto_speak === true) })}
      />

      <button
        type="button"
        onClick={() =>
          speakText("Halo, saya Violet. Ini contoh suara saya.", current)
        }
        className="w-full text-xs font-medium text-steel-highlight bg-steel-highlight/10 hover:bg-steel-highlight/15 border border-steel-highlight/30 rounded-lg py-2 transition"
      >
        Test voice
      </button>
    </div>
  );
}
