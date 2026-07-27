import { Globe } from "lucide-react";
import { SectionHeader } from "../controls/SectionHeader";
import { TextRow } from "../controls/TextRow";
import { ToggleRow } from "../controls/ToggleRow";
import type { PanelProps } from "../SettingsShell";

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
  patch,
  devMode,
  onReset,
}: PanelProps & { onReset: () => void }) {
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
        <ToggleRow
          icon={<Globe size={13} className="text-steel-highlight" />}
          label="Web search"
          on={webSearchEnabled}
          onToggle={() => patch({ web_search_enabled: !webSearchEnabled })}
        />
        {devMode && webSearchEnabled && (
          <TextRow
            label="Web search model"
            value={String(values.web_search_model ?? "")}
            placeholder="web search model"
            onChange={(next) => patch({ web_search_model: next })}
          />
        )}
        <ToggleRow
          label="Canvas mode"
          on={canvasEnabled}
          onToggle={() => patch({ canvas_enabled: !canvasEnabled })}
        />
        <ToggleRow
          label="Ask before saving memory"
          on={memoryApproval}
          onToggle={() => patch({ memory_require_approval: !memoryApproval })}
        />
      </div>
    </div>
  );
}
