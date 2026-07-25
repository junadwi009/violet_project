import type { ReactNode } from "react";
import { X, SlidersHorizontal, Layers, Bot, Sparkles, Globe } from "lucide-react";
// (SkillLab is rendered from App, not here)
import {
  AgentInfo,
  AppSettings,
  KnowledgeInfo,
  PersonalityProfile,
  ProviderInfo,
  RouterInfo,
  SkillInfo,
} from "../lib/api";

type SettingsModalProps = {
  open: boolean;
  onClose: () => void;
  personalities: PersonalityProfile[];
  personalityId: string;
  onSelectPersonality: (id: string) => void;
  providers: ProviderInfo[];
  selectedProvider: string;
  onSelectProvider: (id: string) => void;
  router: RouterInfo | null;
  agents: AgentInfo[];
  selectedAgent: string;
  onSelectAgent: (id: string) => void;
  skills: SkillInfo[];
  settings: AppSettings | null;
  onPatchSettings: (changes: Record<string, string | number | boolean>) => void;
  onOpenSkillLab: () => void;
  knowledge: KnowledgeInfo | null;
  onReindex: (full: boolean) => void;
  devMode: boolean;
};

function personaLabel(profile: PersonalityProfile): string {
  if (profile.id === "violet.devoted_strategist") return "Devoted Strategist";
  return profile.name;
}

function ToggleRow({
  label,
  on,
  onToggle,
  icon,
}: {
  label: string;
  on: boolean;
  onToggle: () => void;
  icon?: ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 text-xs text-steel-dark">
      {icon}
      <span className="font-medium">{label}</span>
      <button
        type="button"
        onClick={onToggle}
        role="switch"
        aria-checked={on}
        className={`ml-auto w-9 h-5 rounded-full transition relative ${
          on ? "bg-steel-highlight" : "bg-navy-700/30"
        }`}
        title={label}
      >
        <span
          className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${
            on ? "left-4" : "left-0.5"
          }`}
        />
      </button>
    </div>
  );
}

export function SettingsModal({
  open,
  onClose,
  personalities,
  personalityId,
  onSelectPersonality,
  providers,
  selectedProvider,
  onSelectProvider,
  router,
  agents,
  selectedAgent,
  onSelectAgent,
  skills,
  settings,
  onPatchSettings,
  onOpenSkillLab,
  knowledge,
  onReindex,
  devMode,
}: SettingsModalProps) {
  if (!open) return null;
  const values = settings?.values;
  const temperature = Number(values?.temperature ?? 0.2);
  const webSearchEnabled = values?.web_search_enabled === true;
  const canvasEnabled = values?.canvas_enabled !== false;
  const memoryApproval = values?.memory_require_approval !== false;
  return (
    <div
      className="fixed inset-0 bg-steel-dark/30 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white border border-navy-700/20 p-8 rounded-[2rem] w-full max-w-md shadow-2xl relative"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-6 right-6 text-steel hover:text-steel-dark"
          title="Close"
        >
          <X size={18} />
        </button>

        <h3 className="text-xl font-semibold text-steel-dark mb-6 flex items-center gap-2">
          <SlidersHorizontal size={18} className="text-steel-highlight" />
          Preferences
        </h3>

        <div className="space-y-6">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-steel uppercase tracking-wider">
              Mode
            </span>
            <div className="ml-auto inline-flex rounded-full bg-steel-ice border border-navy-700/20 p-0.5">
              {(["user", "developer"] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => onPatchSettings({ ui_mode: mode })}
                  className={`px-3 py-1 rounded-full text-xs font-medium capitalize transition ${
                    (settings?.values.ui_mode ?? "user") === mode
                      ? "bg-steel-dark text-white"
                      : "text-steel"
                  }`}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>

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

          {devMode && agents.length > 0 && (
            <div>
              <label className="flex items-center gap-1.5 text-xs font-semibold text-steel uppercase tracking-wider mb-2">
                <Bot size={13} className="text-steel-highlight" />
                Delegate to agent
              </label>
              <div className="grid grid-cols-1 gap-2">
                <button
                  onClick={() => onSelectAgent("")}
                  className={`flex items-center justify-between px-4 py-2.5 rounded-xl border text-sm font-medium transition ${
                    selectedAgent === ""
                      ? "bg-steel-highlight/10 text-steel-highlight border-steel-highlight/30"
                      : "bg-steel-ice text-steel border-navy-700/20 hover:border-steel-highlight/30"
                  }`}
                >
                  <span>Violet (no delegation)</span>
                </button>
                {agents.map((agent) => (
                  <button
                    key={agent.id}
                    onClick={() => onSelectAgent(agent.id)}
                    className={`flex flex-col items-start px-4 py-2.5 rounded-xl border text-sm transition ${
                      agent.id === selectedAgent
                        ? "bg-steel-highlight/10 border-steel-highlight/30"
                        : "bg-steel-ice border-navy-700/20 hover:border-steel-highlight/30"
                    }`}
                  >
                    <span
                      className={`font-medium ${
                        agent.id === selectedAgent ? "text-steel-highlight" : "text-steel-dark"
                      }`}
                    >
                      {agent.name}
                    </span>
                    <span className="text-[11px] text-steel/60 text-left">
                      {agent.description}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {settings && (
            <div>
              <label className="block text-xs font-semibold text-steel uppercase tracking-wider mb-2">
                Behavior
              </label>
              <div className="space-y-3 p-3 bg-steel-ice rounded-xl border border-navy-700/20">
                {devMode && (
                  <div>
                    <div className="flex items-center justify-between text-xs text-steel-dark mb-1">
                      <span className="font-medium">Temperature</span>
                      <span className="font-mono text-steel">{temperature.toFixed(1)}</span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={2}
                      step={0.1}
                      value={temperature}
                      onChange={(e) =>
                        onPatchSettings({ temperature: Number(e.target.value) })
                      }
                      className="w-full accent-steel-highlight"
                    />
                  </div>
                )}

                <ToggleRow
                  icon={<Globe size={13} className="text-steel-highlight" />}
                  label="Web search"
                  on={webSearchEnabled}
                  onToggle={() =>
                    onPatchSettings({ web_search_enabled: !webSearchEnabled })
                  }
                />
                {devMode && webSearchEnabled && (
                  <input
                    value={String(values?.web_search_model ?? "")}
                    onChange={(e) =>
                      onPatchSettings({ web_search_model: e.target.value })
                    }
                    placeholder="web search model"
                    className="w-full text-xs font-mono bg-white border border-navy-700/20 rounded-lg px-2.5 py-1.5 text-steel-dark focus:outline-none focus:ring-1 focus:ring-steel-highlight/30"
                  />
                )}
                <ToggleRow
                  label="Canvas mode"
                  on={canvasEnabled}
                  onToggle={() => onPatchSettings({ canvas_enabled: !canvasEnabled })}
                />
                <ToggleRow
                  label="Ask before saving memory"
                  on={memoryApproval}
                  onToggle={() =>
                    onPatchSettings({ memory_require_approval: !memoryApproval })
                  }
                />
              </div>
            </div>
          )}

          <div>
            <label className="flex items-center gap-1.5 text-xs font-semibold text-steel uppercase tracking-wider mb-2">
              <Sparkles size={13} className="text-steel-highlight" />
              Skills
            </label>
            <div className="space-y-1.5 max-h-40 overflow-y-auto custom-scrollbar p-1">
              {skills.length === 0 && (
                <p className="text-[11px] text-steel/60 px-2 py-1">
                  No skills configured. Type <span className="font-mono">/</span> in the
                  composer to invoke one.
                </p>
              )}
              {skills.map((skill) => (
                <div
                  key={skill.id}
                  className="flex flex-col px-3 py-2 rounded-lg bg-steel-ice border border-navy-700/20"
                >
                  <span className="text-xs font-medium text-steel-dark">
                    /{skill.id} · {skill.name}
                  </span>
                  <span className="text-[11px] text-steel/60">{skill.description}</span>
                </div>
              ))}
            </div>
            {devMode && (
              <button
                onClick={onOpenSkillLab}
                className="mt-2 w-full text-xs font-medium text-steel-highlight bg-steel-highlight/10 hover:bg-steel-highlight/15 border border-steel-highlight/30 rounded-lg py-2 transition"
              >
                Open Skill Lab
              </button>
            )}
          </div>

          {knowledge && (
            <div>
              <label className="block text-xs font-semibold text-steel uppercase tracking-wider mb-2">
                Knowledge base
              </label>
              <div className="p-3 bg-steel-ice rounded-xl border border-navy-700/20 space-y-2">
                <div className="text-[11px] text-steel-dark font-mono truncate">
                  {knowledge.dir}
                </div>
                <div className="text-[11px] text-steel">
                  {knowledge.doc_count} docs · {knowledge.chunk_count} chunks ·{" "}
                  {knowledge.provider}
                </div>
                {!knowledge.enabled && (
                  <div className="text-[11px] text-amber-600">
                    Retrieval off — set RAG_PROVIDER=vector to enable.
                  </div>
                )}
                <div className="flex gap-2">
                  <button
                    onClick={() => onReindex(false)}
                    disabled={!knowledge.enabled}
                    className="flex-1 text-xs font-medium text-steel-highlight bg-steel-highlight/10 hover:bg-steel-highlight/15 border border-steel-highlight/30 rounded-lg py-2 transition disabled:opacity-40"
                  >
                    Reindex
                  </button>
                  {devMode && (
                    <button
                      onClick={() => onReindex(true)}
                      disabled={!knowledge.enabled}
                      className="flex-1 text-xs font-medium text-steel bg-white border border-navy-700/20 rounded-lg py-2 transition disabled:opacity-40"
                    >
                      Full rebuild
                    </button>
                  )}
                </div>
                {devMode && knowledge.docs.length > 0 && (
                  <ul className="max-h-28 overflow-y-auto custom-scrollbar space-y-0.5 pt-1">
                    {knowledge.docs.map((d) => (
                      <li
                        key={d.path}
                        className="text-[11px] text-steel-dark flex justify-between gap-2"
                      >
                        <span className="truncate">{d.path}</span>
                        <span className="text-steel/60 shrink-0">{d.chunk_count}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}

          {devMode && (
          <div>
            <label className="block text-xs font-semibold text-steel uppercase tracking-wider mb-2">
              Palette
            </label>
            <div className="flex items-center gap-3 p-3 bg-steel-ice rounded-xl border border-navy-700/20">
              <div className="flex h-5 w-24 rounded overflow-hidden">
                <div className="flex-1 bg-navy-950" />
                <div className="flex-1 bg-steel-highlight" />
                <div className="flex-1 bg-[#9d4edd]" />
                <div className="flex-1 bg-white" />
              </div>
              <span className="text-xs text-steel-dark font-medium">
                Violet Light
              </span>
            </div>
          </div>
          )}
        </div>

        <button
          onClick={onClose}
          className="w-full bg-steel-dark hover:bg-black text-white font-semibold py-3 px-4 rounded-xl text-sm transition mt-6 shadow-sm"
        >
          Done
        </button>
      </div>
    </div>
  );
}
