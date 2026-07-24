import { X, SlidersHorizontal, Layers, Bot } from "lucide-react";
// (SkillLab is rendered from App, not here)
import { AgentInfo, PersonalityProfile, ProviderInfo, RouterInfo } from "../lib/api";

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
};

function personaLabel(profile: PersonalityProfile): string {
  if (profile.id === "violet.devoted_strategist") return "Devoted Strategist";
  return profile.name;
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
}: SettingsModalProps) {
  if (!open) return null;
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

          {router && router.mode === "cascade" && (
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

          {agents.length > 0 && (
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
