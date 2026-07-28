import { Layers } from "lucide-react";
import type { ProviderInfo, RouterInfo, SettingsValues } from "../../../lib/api";
import { SectionHeader } from "../controls/SectionHeader";
import { SliderRow } from "../controls/SliderRow";
import { TextRow } from "../controls/TextRow";
import type { PanelProps } from "../SettingsShell";

// Exactly `keys_in_group("model")` from `preferences/store.py`. `web_search_model`
// is NOT here: it renders next to the web-search toggle in `BehaviorPanel` and,
// as of Task 13, it groups with `behavior` on the backend too — so that panel
// owns both its dot and its reset.
const MODEL_KEYS = [
  "llm_model",
  "temperature",
  "persona_model",
  "technical_model",
  "artifact_model",
  "vision_model",
  "agent_default_model",
];

export function ModelPanel({
  values,
  overridden,
  patchDebounced,
  devMode,
  providers,
  selectedProvider,
  onSelectProvider,
  router,
  defaults,
  onReset,
}: PanelProps & {
  providers: ProviderInfo[];
  selectedProvider: string;
  onSelectProvider: (id: string) => void;
  router: RouterInfo | null;
  defaults: SettingsValues;
  onReset: () => void;
}) {
  const modified = MODEL_KEYS.some((key) => overridden.includes(key));
  const temperature = Number(values.temperature ?? 0.2);

  // Every section below is `devMode`-gated, so outside developer mode this
  // panel would be a lone header over nothing, with a live "Reset section"
  // button for controls the user cannot see. The nav hides this tab in user
  // mode; this covers the window where the mode flips while it is open.
  if (!devMode) return null;

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Model"
        description="Which engine answers, how it routes, and how loose it is."
        modified={modified}
        onReset={onReset}
      />

      {devMode && (
        <div>
          <label className="block text-xs font-semibold text-steel uppercase tracking-wider mb-2">
            AI engine
          </label>
          <div className="grid grid-cols-1 gap-2">
            {providers.map((provider) => (
              <button
                key={provider.id}
                onClick={() => onSelectProvider(provider.id)}
                className={`flex items-center justify-between px-4 py-2.5 rounded-xl border text-sm font-medium transition ${
                  provider.id === selectedProvider
                    ? "bg-steel-highlight/10 text-steel-highlight border-steel-highlight/30"
                    : "bg-steel-ice text-steel border-navy-700/20 hover:border-steel-highlight/30"
                }`}
              >
                <span>{provider.label}</span>
                {/* `text-steel`, not `text-steel-muted`: this badge sits on the
                    *selected* row, whose `bg-steel-highlight/10` lifts the
                    surface toward the accent and leaves the tertiary ink at
                    4.50:1 — right on the line. `steel` is 6.15:1 there. */}
                {provider.active && (
                  <span className="text-[10px] uppercase tracking-wider text-steel">
                    server default
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {devMode && (
        <div className="p-3 bg-steel-ice rounded-xl border border-navy-700/20">
          <SliderRow
            label="Temperature"
            value={temperature}
            min={0}
            max={2}
            step={0.1}
            // `SliderRow` holds its own value, so the debounce is invisible
            // here and saves a request per 0.1 step of the drag.
            onChange={(next) => patchDebounced({ temperature: next })}
          />
        </div>
      )}

      {devMode && router?.mode === "cascade" && (
        <div className="space-y-3 p-3 bg-steel-ice rounded-xl border border-navy-700/20">
          <label className="flex items-center gap-2 text-xs font-semibold text-steel uppercase tracking-wider">
            <Layers size={13} className="text-steel-highlight shrink-0" />
            Routing · cascade
          </label>
          <p className="text-[11px] text-steel-muted">
            Persona answers; heavy calculation and code are delegated to the technical
            layer on demand. Blank falls back to the server default.
          </p>
          <TextRow
            label="Persona model"
            value={String(values.persona_model ?? "")}
            placeholder={String(defaults.persona_model ?? "")}
            onChange={(persona_model) => patchDebounced({ persona_model })}
          />
          <TextRow
            label="Technical model"
            value={String(values.technical_model ?? "")}
            placeholder={String(defaults.technical_model ?? "")}
            onChange={(technical_model) => patchDebounced({ technical_model })}
          />
        </div>
      )}

      {devMode && (
        <TextRow
          label="Artifact model"
          value={String(values.artifact_model ?? "")}
          placeholder={String(defaults.artifact_model ?? "")}
          hint="Generates canvas artifacts."
          onChange={(artifact_model) => patchDebounced({ artifact_model })}
        />
      )}
      {devMode && (
        <TextRow
          label="Vision model"
          value={String(values.vision_model ?? "")}
          placeholder={String(defaults.vision_model ?? "")}
          hint="Reads uploaded images and scanned PDFs."
          onChange={(vision_model) => patchDebounced({ vision_model })}
        />
      )}
      {devMode && (
        <TextRow
          label="Default agent model"
          value={String(values.agent_default_model ?? "")}
          placeholder={String(defaults.agent_default_model ?? "")}
          hint="Used by agents that do not pin their own model."
          onChange={(agent_default_model) => patchDebounced({ agent_default_model })}
        />
      )}
    </div>
  );
}
