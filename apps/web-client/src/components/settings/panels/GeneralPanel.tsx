import type { PersonalityProfile } from "../../../lib/api";
import { SectionHeader } from "../controls/SectionHeader";
import { SegmentedRow } from "../controls/SegmentedRow";
import type { PanelProps } from "../SettingsShell";

const GENERAL_KEYS = ["ui_mode", "default_personality", "default_provider"];

// Mirrors the backend `_choice("user", "developer")` validator, so the value
// handed to `SegmentedRow` is never outside `options` (which would silently
// report the first option as checked).
const MODE_OPTIONS = [
  { value: "user", label: "User" },
  { value: "developer", label: "Developer" },
] as const;

type Mode = (typeof MODE_OPTIONS)[number]["value"];

function personaLabel(profile: PersonalityProfile): string {
  if (profile.id === "violet.devoted_strategist") return "Devoted Strategist";
  return profile.name;
}

export function GeneralPanel({
  values,
  overridden,
  patch,
  personalities,
  personalityId,
  onSelectPersonality,
  onReset,
}: PanelProps & {
  personalities: PersonalityProfile[];
  personalityId: string;
  onSelectPersonality: (id: string) => void;
  onReset: () => void;
}) {
  const modified = GENERAL_KEYS.some((key) => overridden.includes(key));
  const mode: Mode = values.ui_mode === "developer" ? "developer" : "user";

  return (
    <div className="space-y-6">
      <SectionHeader
        title="General"
        description="Interface mode and the persona Violet answers as."
        modified={modified}
        onReset={onReset}
      />

      <SegmentedRow
        label="Mode"
        value={mode}
        options={MODE_OPTIONS}
        onSelect={(next) => patch({ ui_mode: next })}
      />

      <div>
        <label className="block text-xs font-semibold text-steel uppercase tracking-wider mb-2">
          Persona
        </label>
        <div className="grid grid-cols-2 gap-2">
          {personalities.map((profile) => (
            <button
              key={profile.id}
              onClick={() => onSelectPersonality(profile.id)}
              className={`px-3 py-2 rounded-lg text-xs font-medium border transition ${
                profile.id === personalityId
                  ? "bg-steel-highlight/10 text-steel-highlight border-steel-highlight/30"
                  : "bg-steel-ice text-steel border-navy-700/20 hover:border-steel-highlight/30"
              }`}
            >
              {personaLabel(profile)}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
