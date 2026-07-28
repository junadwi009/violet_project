import { Bot } from "lucide-react";
import type { AgentInfo } from "../../../lib/api";
import { SectionHeader } from "../controls/SectionHeader";
import type { PanelProps } from "../SettingsShell";

export function AgentsPanel({
  devMode,
  agents,
  selectedAgent,
  onSelectAgent,
}: PanelProps & {
  agents: AgentInfo[];
  selectedAgent: string;
  onSelectAgent: (id: string) => void;
}) {
  // Delegation is per-session client state, not a stored preference, so there is
  // no settings group to reset.
  return (
    <div className="space-y-6">
      <SectionHeader
        title="Agents"
        description="Hand the next turn to a specialised agent instead of Violet."
        modified={false}
      />

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
                <span className="text-[11px] text-steel-muted text-left">
                  {agent.description}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
