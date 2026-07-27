import { Layers } from "lucide-react";
import type { ProviderInfo, RouterInfo } from "../../../lib/api";
import { SectionHeader } from "../controls/SectionHeader";
import { SliderRow } from "../controls/SliderRow";
import type { PanelProps } from "../SettingsShell";

// Exactly `keys_in_group("model")` from `preferences/store.py`. That includes
// `web_search_model`, which *renders* next to the web-search toggle in
// `BehaviorPanel` but is reset by this panel's button — so this panel is the one
// that must show the dot for it. Task 12/13 decides where the input lives.
const MODEL_KEYS = [
  "llm_model",
  "temperature",
  "web_search_model",
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
  onReset,
}: PanelProps & {
  providers: ProviderInfo[];
  selectedProvider: string;
  onSelectProvider: (id: string) => void;
  router: RouterInfo | null;
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
                {provider.active && (
                  <span className="text-[10px] uppercase tracking-wider text-steel/50">
                    server default
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {devMode && router && router.mode === "cascade" && (
        <div>
          <label className="block text-xs font-semibold text-steel uppercase tracking-wider mb-2">
            Routing · cascade
          </label>
          <div className="space-y-1.5 p-3 bg-steel-ice rounded-xl border border-navy-700/20">
            <div className="flex items-center gap-2 text-xs text-steel-dark">
              <Layers size={13} className="text-steel-highlight shrink-0" />
              <span className="font-medium">Persona</span>
              <span className="ml-auto font-mono text-[11px] text-steel truncate max-w-[190px]">
                {router.persona_model}
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-steel-dark">
              <Layers size={13} className="text-steel/50 shrink-0" />
              <span className="font-medium">Technical</span>
              <span className="ml-auto font-mono text-[11px] text-steel truncate max-w-[190px]">
                {router.technical_model}
              </span>
            </div>
            <p className="text-[10px] text-steel/60 pt-1">
              Persona answers; delegates heavy calc/code to the technical layer on demand.
            </p>
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
    </div>
  );
}
