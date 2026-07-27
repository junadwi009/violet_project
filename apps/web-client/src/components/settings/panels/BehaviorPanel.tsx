import { Globe } from "lucide-react";
import type { SettingsValues } from "../../../lib/api";
import { SectionHeader } from "../controls/SectionHeader";
import { TextRow } from "../controls/TextRow";
import { ToggleRow } from "../controls/ToggleRow";
import type { PanelProps } from "../SettingsShell";

// Exactly `keys_in_group("behavior")` from `preferences/store.py`, so the dot
// and the "Reset section" button describe what the reset will actually do.
// `web_search_model` renders below, next to the toggle that gates it, and as
// of Task 13 it groups with `behavior` on the backend too — so this panel now
// owns both its dot and its reset; `ModelPanel` no longer claims it.
const BEHAVIOR_KEYS = [
  "web_search_enabled",
  "web_search_model",
  "canvas_enabled",
  "memory_require_approval",
  "memory_auto_save",
];

export function BehaviorPanel({
  values,
  overridden,
  patchDebounced,
  patchNow,
  devMode,
  defaults,
  onReset,
}: PanelProps & { defaults: SettingsValues; onReset: () => void }) {
  const modified = BEHAVIOR_KEYS.some((key) => overridden.includes(key));
  const webSearchEnabled = values.web_search_enabled === true;
  const canvasEnabled = values.canvas_enabled !== false;
  const memoryApproval = values.memory_require_approval !== false;

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Behavior"
        description="What Violet is allowed to reach for while answering."
        modified={modified}
        onReset={onReset}
      />

      <div className="space-y-3 p-3 bg-steel-ice rounded-xl border border-navy-700/20">
        {/* The toggles patch through `patchNow`: they show `values`, not local
            state, and `!current` reads the value they render from. Debounced,
            the switch would lag the click by the whole window and two rapid
            taps would collapse into one flip. Only `TextRow` below, which has
            its own local state, uses `patchDebounced`. */}
        <ToggleRow
          icon={<Globe size={13} className="text-steel-highlight" />}
          label="Web search"
          on={webSearchEnabled}
          onToggle={() => patchNow({ web_search_enabled: !webSearchEnabled })}
        />
        {devMode && webSearchEnabled && (
          <TextRow
            label="Web search model"
            value={String(values.web_search_model ?? "")}
            placeholder={String(defaults.web_search_model ?? "")}
            onChange={(next) => patchDebounced({ web_search_model: next })}
          />
        )}
        <ToggleRow
          label="Canvas mode"
          on={canvasEnabled}
          onToggle={() => patchNow({ canvas_enabled: !canvasEnabled })}
        />
        <ToggleRow
          label="Ask before saving memory"
          on={memoryApproval}
          onToggle={() => patchNow({ memory_require_approval: !memoryApproval })}
        />
      </div>
    </div>
  );
}
