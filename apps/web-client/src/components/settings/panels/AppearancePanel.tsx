import type { PanelProps } from "../SettingsShell";
import { SectionHeader } from "../controls/SectionHeader";
import { SegmentedRow } from "../controls/SegmentedRow";
import { SliderRow } from "../controls/SliderRow";
import type { AccentChoice, DensityChoice, ThemeChoice } from "../../../lib/theme";
import { DEFAULT_APPEARANCE } from "../../../lib/theme";

const APPEARANCE_KEYS = ["theme", "ui_density", "font_scale", "accent"];

const THEME_OPTIONS = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
] as const;

const DENSITY_OPTIONS = [
  { value: "cozy", label: "Cozy" },
  { value: "compact", label: "Compact" },
] as const;

// Deliberate exception to the "no hardcoded colours" rule (see CLAUDE.md /
// task brief): these swatches must show each accent's TRUE hue in both
// themes, so they cannot be themed tokens. Task 17's dark-mode contrast sweep
// should skip this block.
const ACCENTS: { value: AccentChoice; label: string; swatch: string }[] = [
  { value: "violet", label: "Violet", swatch: "#7b2cbf" },
  { value: "indigo", label: "Indigo", swatch: "#4f46e5" },
  { value: "teal", label: "Teal", swatch: "#0d9488" },
  { value: "amber", label: "Amber", swatch: "#b45309" },
  { value: "rose", label: "Rose", swatch: "#be123c" },
];

export function AppearancePanel({
  values,
  overridden,
  patchNow,
  patchDebounced,
  onReset,
}: PanelProps & { onReset: () => void }) {
  const modified = APPEARANCE_KEYS.some((key) => overridden.includes(key));

  // `theme` and `ui_density` come from server state, not a local click
  // handler, so an unexpected value (a hand-edited preferences.json, a stale
  // cache) is possible even though the backend validates on write. Coerce
  // explicitly to a known option rather than handing the raw value to
  // `SegmentedRow`: it reports the *first* option as checked for anything
  // outside `options`, and "system" is not first, so an out-of-range theme
  // would silently render as "Light" selected while the page is actually
  // following the OS. Falling back to the same default `appearanceFromSettings`
  // uses keeps the displayed selection truthful to what's on screen.
  const theme: ThemeChoice = THEME_OPTIONS.some((option) => option.value === values.theme)
    ? (values.theme as ThemeChoice)
    : DEFAULT_APPEARANCE.theme;

  const density: DensityChoice = DENSITY_OPTIONS.some(
    (option) => option.value === values.ui_density,
  )
    ? (values.ui_density as DensityChoice)
    : DEFAULT_APPEARANCE.density;

  const accent: AccentChoice = ACCENTS.some((option) => option.value === values.accent)
    ? (values.accent as AccentChoice)
    : DEFAULT_APPEARANCE.accent;

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Appearance"
        description="Applies immediately and follows you to any browser signed in to this assistant."
        modified={modified}
        onReset={onReset}
      />

      <SegmentedRow
        label="Theme"
        value={theme}
        options={THEME_OPTIONS}
        // Click-driven, rendered straight from `values` — patch immediately.
        // See the `patchNow` vs `patchDebounced` note on `PanelProps`.
        onSelect={(next) => patchNow({ theme: next })}
      />

      <SegmentedRow
        label="Density"
        value={density}
        options={DENSITY_OPTIONS}
        onSelect={(next) => patchNow({ ui_density: next })}
      />

      <SliderRow
        label="Font size"
        value={Number(values.font_scale ?? DEFAULT_APPEARANCE.fontScale)}
        min={0.875}
        max={1.25}
        step={0.025}
        format={(value) => `${Math.round(value * 16)}px`}
        // Holds local state and fires continuously while dragging — debounce
        // so a drag coalesces into one PATCH instead of one per step.
        onChange={(font_scale) => patchDebounced({ font_scale })}
      />

      <div>
        <span className="block text-xs font-medium text-steel-dark mb-2">Accent</span>
        <div className="flex items-center gap-2">
          {ACCENTS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => patchNow({ accent: option.value })}
              aria-label={option.label}
              aria-pressed={option.value === accent}
              title={option.label}
              className={`w-7 h-7 rounded-full border-2 transition ${
                option.value === accent
                  ? "border-steel-dark scale-110"
                  : "border-transparent hover:scale-105"
              }`}
              // Hardcoded hex on purpose — see the comment on `ACCENTS` above.
              style={{ backgroundColor: option.swatch }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
