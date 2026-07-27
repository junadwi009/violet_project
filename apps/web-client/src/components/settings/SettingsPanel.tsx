import { useState } from "react";
import {
  Bot,
  Database,
  Globe,
  Layers,
  Mic,
  Palette,
  Settings2,
  Shield,
  Sparkles,
} from "lucide-react";
import {
  resetSettings,
  type AgentInfo,
  type AppSettings,
  type KnowledgeInfo,
  type PersonalityProfile,
  type ProviderInfo,
  type RouterInfo,
  type SettingsGroup,
  type SettingsValues,
  type SkillInfo,
} from "../../lib/api";
import { SettingsNav, type NavItem } from "./SettingsNav";
import { SettingsShell } from "./SettingsShell";
import { useDebouncedPatch } from "./useDebouncedPatch";
import { AgentsPanel } from "./panels/AgentsPanel";
import { BehaviorPanel } from "./panels/BehaviorPanel";
import { GeneralPanel } from "./panels/GeneralPanel";
import { KnowledgePanel } from "./panels/KnowledgePanel";
import { ModelPanel } from "./panels/ModelPanel";
import { SkillsPanel } from "./panels/SkillsPanel";

const NAV: NavItem[] = [
  { id: "general", label: "General", icon: <Settings2 size={14} /> },
  { id: "appearance", label: "Appearance", icon: <Palette size={14} /> },
  { id: "behavior", label: "Behavior", icon: <Globe size={14} /> },
  { id: "voice", label: "Voice", icon: <Mic size={14} /> },
  { id: "knowledge", label: "Knowledge", icon: <Database size={14} /> },
  { id: "skills", label: "Skills", icon: <Sparkles size={14} /> },
  { id: "data", label: "Data & privacy", icon: <Shield size={14} /> },
  { id: "model", label: "Model", icon: <Layers size={14} />, devOnly: true },
  { id: "agents", label: "Agents", icon: <Bot size={14} />, devOnly: true },
];

export type SettingsPanelProps = {
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
  onPatchSettings: (changes: SettingsValues) => void;
  onOpenSkillLab: () => void;
  knowledge: KnowledgeInfo | null;
  onReindex: (full: boolean, source?: string) => void;
  onConnectGDrive: () => void;
  onDisconnectGDrive: () => void;
  devMode: boolean;
  /** Wired up by Task 15's Data & privacy panel; declared here so the prop
   *  contract Task 16 depends on is already in place. */
  onDeleteAllSessions?: () => void;
};

export function SettingsPanel({
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
  onConnectGDrive,
  onDisconnectGDrive,
  devMode,
}: SettingsPanelProps) {
  const [activeTab, setActiveTab] = useState("general");
  const [error, setError] = useState<string | null>(null);

  // One debouncer for the whole dialog, so a slider drag and the text field
  // next to it coalesce into a single PATCH.
  const { push, flush } = useDebouncedPatch(onPatchSettings);

  const values = settings?.values ?? {};
  const overridden = settings?.overridden ?? [];

  // `useDebouncedPatch` flushes on *unmount*, and this component never unmounts
  // — App renders it unconditionally and only toggles `open`. So closing is
  // flushed explicitly here. Every dismissal path (backdrop, X, Escape) goes
  // through the shell's `onClose`, which is this function.
  function handleClose() {
    flush();
    onClose();
  }

  async function handleReset(group: SettingsGroup) {
    try {
      setError(null);
      // A reset invalidates whatever is queued for the same group.
      flush();
      await resetSettings({ group });
      // App owns `appSettings`; the only channel back to it is
      // `onPatchSettings`. An empty PATCH is a server-side no-op that still
      // returns the full post-reset payload, so App re-renders with the
      // defaults restored.
      onPatchSettings({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    }
  }

  const panelProps = { values, overridden, patch: push, devMode };

  function renderPanel() {
    switch (activeTab) {
      case "general":
        return (
          <GeneralPanel
            {...panelProps}
            personalities={personalities}
            personalityId={personalityId}
            onSelectPersonality={onSelectPersonality}
            onReset={() => handleReset("general")}
          />
        );
      case "behavior":
        return (
          <BehaviorPanel
            {...panelProps}
            onReset={() => handleReset("behavior")}
          />
        );
      case "knowledge":
        return (
          <KnowledgePanel
            {...panelProps}
            knowledge={knowledge}
            onReindex={onReindex}
            onConnectGDrive={onConnectGDrive}
            onDisconnectGDrive={onDisconnectGDrive}
            onReset={() => handleReset("knowledge")}
          />
        );
      case "skills":
        return (
          <SkillsPanel
            {...panelProps}
            skills={skills}
            onOpenSkillLab={onOpenSkillLab}
          />
        );
      case "model":
        return (
          <ModelPanel
            {...panelProps}
            providers={providers}
            selectedProvider={selectedProvider}
            onSelectProvider={onSelectProvider}
            router={router}
            onReset={() => handleReset("model")}
          />
        );
      case "agents":
        return (
          <AgentsPanel
            {...panelProps}
            agents={agents}
            selectedAgent={selectedAgent}
            onSelectAgent={onSelectAgent}
          />
        );
      default:
        return <p className="text-xs text-steel">Coming in the next task.</p>;
    }
  }

  return (
    <SettingsShell
      open={open}
      onClose={handleClose}
      title="Settings"
      activeTab={activeTab}
      error={error}
      nav={
        <SettingsNav
          items={NAV}
          active={activeTab}
          onSelect={setActiveTab}
          devMode={devMode}
        />
      }
    >
      {renderPanel()}
    </SettingsShell>
  );
}
