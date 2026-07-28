import { useEffect, useState } from "react";
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
import { AppearancePanel } from "./panels/AppearancePanel";
import { BehaviorPanel } from "./panels/BehaviorPanel";
import { DataPanel } from "./panels/DataPanel";
import { GeneralPanel } from "./panels/GeneralPanel";
import { KnowledgePanel } from "./panels/KnowledgePanel";
import { ModelPanel } from "./panels/ModelPanel";
import { SkillsPanel } from "./panels/SkillsPanel";
import { VoicePanel } from "./panels/VoicePanel";

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
  /** Last failed preference write, owned by App because `onPatchSettings`
   *  resolves to `void` and swallows its own error — this panel cannot observe
   *  the failure itself. Rendered in the shell's error slot alongside reset
   *  failures, because App's status pill sits in `WorkspaceHeader`, which the
   *  settings scrim covers and blurs while the dialog is open. */
  patchError: string | null;
  /** App owns `appSettings`. A group reset returns the full post-reset payload
   *  on its own response, so hand it back through here rather than firing a
   *  second request just to re-read what we already have. Named for the event,
   *  not for "settings changed in general": App also uses it to resync the
   *  persona/provider it holds outside `values`, which is only correct as a
   *  one-shot on a reset — see the handler in App.tsx. */
  onSettingsReset: (next: AppSettings) => void;
  onOpenSkillLab: () => void;
  knowledge: KnowledgeInfo | null;
  onReindex: (full: boolean, source?: string) => void;
  onConnectGDrive: () => void;
  onDisconnectGDrive: () => void;
  devMode: boolean;
  /** Runs the destructive clear behind the Data & privacy panel's inline typed
   *  confirmation. App owns it because the aftermath is App's state: the
   *  session list, the open conversation, and the memory drawer all have to be
   *  re-read once the rows are gone. */
  onDeleteAllSessions: () => Promise<void>;
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
  patchError,
  onSettingsReset,
  onOpenSkillLab,
  knowledge,
  onReindex,
  onConnectGDrive,
  onDisconnectGDrive,
  devMode,
  onDeleteAllSessions,
}: SettingsPanelProps) {
  const [activeTab, setActiveTab] = useState("general");
  const [error, setError] = useState<string | null>(null);

  // One debouncer for the whole dialog, so a slider drag and the text field
  // next to it coalesce into a single PATCH.
  const { push, flush, cancel } = useDebouncedPatch(onPatchSettings);

  const values = settings?.values ?? {};
  const overridden = settings?.overridden ?? [];
  const defaults = settings?.defaults ?? {};

  // Reopening lands on General rather than wherever the last visit ended:
  // Settings is entered from one generic trigger with no memory of intent, so
  // the last tab is not a better guess than the first, and a dialog that opens
  // somewhere different each time is harder to navigate by muscle memory.
  // Keyed on `open` rather than done in `handleClose` so the paths that bypass
  // it are covered too — App closes Settings itself when the Skill Lab opens.
  useEffect(() => {
    if (!open) setActiveTab("general");
  }, [open]);

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
      // Discard the queue, do NOT flush it. A reset supersedes whatever is
      // pending; flushing would put a PATCH in flight alongside the reset with
      // no ordering guarantee, and a PATCH landing second silently undoes it.
      cancel();
      // `resetSettings` already resolves to the full post-reset payload, so
      // hand that straight to App. (An earlier version PATCHed `{}` to re-read
      // it — not the no-op it looked like: `PreferencesStore.patch` rewrites
      // preferences.json unconditionally, which creates the file when absent,
      // strips hand-added unknown keys, and clobbers an unparseable file
      // with `{}`.)
      onSettingsReset(await resetSettings({ group }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    }
  }

  // Two write channels, deliberately not one.
  //
  // `patchNow` is the default for anything click-driven. `ToggleRow` and
  // `SegmentedRow` derive what they display purely from `values`, which only
  // changes when the PATCH response lands — so debouncing them does not hide
  // latency, it *adds* the whole window to it, and their `!current` handlers
  // close over server state that has not moved yet, so two taps inside one
  // window compute the same payload and coalesce into a single net flip.
  //
  // `patchDebounced` is only for `SliderRow` / `TextRow`, which render from
  // their own local state and would otherwise emit one request and one JSON
  // file write per keystroke or per 0.1 of temperature drag.
  const panelProps = {
    values,
    overridden,
    patchDebounced: push,
    patchNow: onPatchSettings,
    devMode,
  };

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
      case "appearance":
        return (
          <AppearancePanel
            {...panelProps}
            onReset={() => handleReset("appearance")}
          />
        );
      case "behavior":
        return (
          <BehaviorPanel
            {...panelProps}
            defaults={defaults}
            onReset={() => handleReset("behavior")}
          />
        );
      case "voice":
        return (
          <VoicePanel {...panelProps} onReset={() => handleReset("voice")} />
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
      case "data":
        // Deliberately NOT spread with `panelProps`: this panel writes no
        // preferences, so `values` / `overridden` / the two patch channels
        // would all be dead props on it.
        return (
          <DataPanel
            locked={settings?.locked ?? {}}
            onDeleteAllSessions={onDeleteAllSessions}
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
            defaults={defaults}
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
      // Reset failures are local to this component; ordinary write failures
      // arrive from App. A reset error wins because it is the more recent,
      // more deliberate action when both are present.
      error={error ?? patchError}
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
