import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  AgentInfo,
  AppSettings,
  ChatMessage,
  Memory,
  MemoryCandidate,
  MemoryInfo,
  PersonalityProfile,
  KnowledgeInfo,
  ProviderInfo,
  RouterInfo,
  SessionSummary,
  SkillInfo,
  approveMemoryCandidate,
  connectGDrive,
  deleteAllSessions,
  deleteMemory,
  disconnectGDrive,
  fetchAgents,
  fetchKnowledge,
  fetchMemories,
  fetchMemoryCandidates,
  fetchMemoryInfo,
  fetchPersonalities,
  fetchProviders,
  fetchSessionMessages,
  fetchSessions,
  fetchSettings,
  fetchSkills,
  patchSettings,
  reindexKnowledge,
  rejectMemoryCandidate,
  resumeAgentRun,
  sendChat,
  updateMemory,
  updateMemoryCandidate,
  uploadFile,
} from "./lib/api";
import {
  canRecognizeSpeech,
  canSpeak,
  createSpeechRecognizer,
  DEFAULT_VOICE,
  speakText,
  stopSpeaking,
  type VoiceSettings,
} from "./lib/speech";
import { AvatarEmotion, AvatarState, normalizeEmotion } from "./lib/avatar";
import {
  appearanceFromSettings,
  applyAppearance,
  watchSystemTheme,
  writeCachedAppearance,
} from "./lib/theme";
import { Sidebar } from "./components/Sidebar";
import { WorkspaceHeader } from "./components/WorkspaceHeader";
import { EmptyState } from "./components/EmptyState";
import { ChatTimeline } from "./components/ChatTimeline";
import { Composer } from "./components/Composer";
import { AvatarPresence } from "./components/AvatarPresence";
import { VoiceOverlay } from "./components/VoiceOverlay";
import { FloatingTools } from "./components/FloatingTools";
import { MemoryDrawer } from "./components/MemoryDrawer";
import { SettingsPanel } from "./components/settings/SettingsPanel";
import { HelpModal } from "./components/HelpModal";
import { SkillLab } from "./components/SkillLab";
import { CanvasPanel } from "./components/CanvasPanel";

type Status = {
  tone: "idle" | "busy" | "ok" | "error";
  text: string;
};

function shortProviderLabel(id: string): string {
  if (id === "mock") return "Mock";
  if (id === "openai_compatible") return "Local";
  return id;
}

// The invariant every path that sets `personalityId` / `selectedProvider` has
// to uphold: the id in state is always one the server actually offers. A
// preference the server happily stores (`_is_str` accepts any string for
// `default_personality` / `default_provider`) can name a profile or provider
// that no longer exists — a persona id that doesn't resolve makes
// `POST /api/chat` fail with `FileNotFoundError` from the profile loader and
// leaves the persona picker with nothing selected, since it renders selection
// by comparing against the fetched list.
//
// `desired` is the incoming preference (stored, at bootstrap; post-reset, on a
// group reset), `current` is what state holds now, `fallback` is the server's
// own answer for "which one is really active". With nothing fetched there is
// nothing to validate against, so `current` stands.
function resolveOffered(
  desired: string,
  current: string,
  offered: readonly { id: string }[],
  fallback: string,
): string {
  if (offered.length === 0) return current;
  if (desired && offered.some((item) => item.id === desired)) return desired;
  if (offered.some((item) => item.id === current)) return current;
  if (fallback && offered.some((item) => item.id === fallback)) return fallback;
  return offered[0].id;
}

// Single source of truth for turning stored preferences into the shape
// `speakText` / `createSpeechRecognizer` expect, so every call site agrees on
// what "current voice settings" means instead of re-reading `appSettings`
// with its own defaults inline.
function voiceSettingsFromValues(settings: AppSettings | null): VoiceSettings {
  if (!settings) return DEFAULT_VOICE;
  const { values } = settings;
  return {
    lang: String(values.voice_lang ?? DEFAULT_VOICE.lang),
    voiceName: String(values.voice_name ?? DEFAULT_VOICE.voiceName),
    rate: Number(values.voice_rate ?? DEFAULT_VOICE.rate),
    pitch: Number(values.voice_pitch ?? DEFAULT_VOICE.pitch),
  };
}

export function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [speechOutputEnabled, setSpeechOutputEnabled] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [avatarState, setAvatarState] = useState<AvatarState>("idle");
  const [avatarEmotion, setAvatarEmotion] = useState<AvatarEmotion>("neutral");
  const [status, setStatus] = useState<Status>({ tone: "idle", text: "Ready" });
  /** Last failed preference write, shown inside the Settings dialog. Separate
   *  from `status` because the status pill is behind the settings scrim. */
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [personalities, setPersonalities] = useState<PersonalityProfile[]>([]);
  const [personalityId, setPersonalityId] = useState("violet.default");
  const [candidates, setCandidates] = useState<MemoryCandidate[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [memoryInfo, setMemoryInfo] = useState<MemoryInfo | null>(null);
  const [attachment, setAttachment] = useState<{
    filename: string;
    text: string;
    ocr: boolean;
  } | null>(null);
  const [attaching, setAttaching] = useState(false);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState("mock");
  const [routerInfo, setRouterInfo] = useState<RouterInfo | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [skillLabOpen, setSkillLabOpen] = useState(false);
  const [activeSkill, setActiveSkill] = useState<{ id: string; name: string } | null>(null);
  const [webSearchOn, setWebSearchOn] = useState(false);
  const [appSettings, setAppSettings] = useState<AppSettings | null>(null);
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [canvasOpen, setCanvasOpen] = useState(false);
  const [canvasArtifactId, setCanvasArtifactId] = useState<string | null>(null);
  const [knowledge, setKnowledge] = useState<KnowledgeInfo | null>(null);
  const [decisionBusy, setDecisionBusy] = useState(false);

  const recognizerRef = useRef<ReturnType<typeof createSpeechRecognizer>>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  // The composer's speak toggle is session-local state, but it should track
  // the persisted `auto_speak` preference rather than always defaulting to
  // off (or freezing at whatever it was on first load) — otherwise a user
  // who turns auto-speak on in Settings, without ever touching the composer
  // button, sees the button keep lying ("Enable speech output") while
  // replies still don't speak. So `speechOutputEnabled` keeps following
  // `auto_speak` on every settings refresh until the user *deliberately taps
  // the composer button* — this ref records that tap (set in
  // `handleSpeechOutputToggle`), and once it's true a later settings refresh
  // (e.g. after a group reset) never clobbers the user's explicit choice.
  const speechOutputTappedRef = useRef(false);
  // The server's active provider, kept for `resolveOffered`'s fallback slot on
  // paths that run long after the bootstrap fetch (the group-reset resync).
  // A ref, not state: nothing renders it.
  const activeProviderRef = useRef("mock");

  const speechInputAvailable = canRecognizeSpeech();
  const speechOutputAvailable = canSpeak();
  const isNewChat = messages.length === 0;
  const canSend =
    (draft.trim().length > 0 || attachment !== null) && status.tone !== "busy";

  async function handleAttach(file: File) {
    setAttaching(true);
    setStatus({ tone: "busy", text: `Reading ${file.name}` });
    try {
      const result = await uploadFile(file);
      setAttachment({
        filename: result.filename,
        text: result.text,
        ocr: result.ocr,
      });
      setStatus({
        tone: "ok",
        text: result.ocr
          ? `OCR extracted ${result.chars} chars`
          : `Attached ${result.filename} (${result.chars} chars)`,
      });
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Upload failed",
      });
    } finally {
      setAttaching(false);
    }
  }

  const assistantName = useMemo(() => {
    const profile = personalities.find((item) => item.id === personalityId);
    return profile?.name?.trim() || "Violet";
  }, [personalities, personalityId]);

  const sessionLabel = useMemo(() => {
    if (isNewChat) return "New session";
    if (!sessionId) return "New session";
    return sessionId.slice(0, 8);
  }, [isNewChat, sessionId]);

  async function refreshMemory() {
    const [nextCandidates, nextMemories] = await Promise.all([
      fetchMemoryCandidates(),
      fetchMemories(),
    ]);
    setCandidates(nextCandidates);
    setMemories(nextMemories);
  }

  async function refreshSessions() {
    try {
      setSessions(await fetchSessions());
    } catch {
      /* sessions are non-critical for chat */
    }
  }

  useEffect(() => {
    // One settings request, consumed twice on purpose.
    //
    // `setAppSettings` is independent: theme, dev mode and every panel read it
    // and none of them care about personalities or providers, so it lands as
    // soon as the response does even if another bootstrap request fails.
    //
    // Seeding `personalityId` / `selectedProvider` from the same payload is
    // NOT independent — it has to happen in the same ordered step as
    // validating them against the fetched lists, so `Promise.all` below waits
    // on this promise too.
    const settingsPromise = fetchSettings().catch(() => null);
    settingsPromise.then(setAppSettings);

    Promise.all([
      refreshMemory(),
      fetchPersonalities(),
      fetchProviders(),
      fetchSessions(),
      settingsPromise,
    ])
      .then(([, nextPersonalities, providerResponse, nextSessions, settings]) => {
        setPersonalities(nextPersonalities);
        setProviders(providerResponse.items);
        setRouterInfo(providerResponse.router ?? null);
        setSessions(nextSessions);
        activeProviderRef.current = providerResponse.active;

        // Seed-then-validate as ONE step, not two racing ones.
        //
        // An earlier version seeded these from a separate `fetchSettings()`
        // promise chain and validated them in this one. Both orderings were
        // reachable: with `/api/settings` slow, seed-then-validate corrected a
        // dead stored id; with `/api/personalities` slow, validate-then-seed
        // let it survive — persona picker with nothing selected, and every
        // `POST /api/chat` 500ing out of the profile loader. Functional
        // updaters do not fix that: they guarantee the guard reads current
        // state *when it runs*, not that it runs *after* the seed. Awaiting
        // the same promise removes the ordering question instead of guarding
        // against it.
        setPersonalityId((current) =>
          resolveOffered(
            String(settings?.values.default_personality ?? ""),
            current,
            nextPersonalities,
            "",
          ),
        );
        // Same for a stored `default_provider` that is no longer offered
        // (removed or renamed server-side). Milder — the backend degrades
        // gracefully on an unknown provider — but it renders the raw id as
        // the composer's provider chip instead of a label. The server's
        // active provider is the fallback, not an unconditional override.
        setSelectedProvider((current) =>
          resolveOffered(
            String(settings?.values.default_provider ?? ""),
            current,
            providerResponse.items,
            providerResponse.active,
          ),
        );
      })
      .catch((error: Error) => setStatus({ tone: "error", text: error.message }));
    fetchMemoryInfo()
      .then(setMemoryInfo)
      .catch(() => setMemoryInfo(null));
    fetchAgents()
      .then((response) => setAgents(response.enabled ? response.items : []))
      .catch(() => setAgents([]));
    fetchSkills()
      .then((response) => setSkills(response.enabled ? response.items : []))
      .catch(() => setSkills([]));
    fetchKnowledge()
      .then(setKnowledge)
      .catch(() => setKnowledge(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!appSettings) return;
    const appearance = appearanceFromSettings(appSettings.values);
    applyAppearance(appearance);
    writeCachedAppearance(appearance);
    if (appearance.theme !== "system") return;
    // Follow OS changes while the app is open.
    return watchSystemTheme(() => applyAppearance(appearance));
  }, [appSettings]);

  useEffect(() => {
    if (!appSettings || speechOutputTappedRef.current) return;
    setSpeechOutputEnabled(appSettings.values.auto_speak === true);
  }, [appSettings]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, status.tone]);

  async function send(content: string) {
    const typed = content.trim();
    const current = attachment;
    if (!typed && !current) return;

    const displayContent = current
      ? `${typed}${typed ? "\n" : ""}📎 ${current.filename}`
      : typed;
    const sentContent = current
      ? `[Attached file: ${current.filename}${current.ocr ? " (OCR text)" : ""}]\n${current.text}\n\n${typed || "Use this file."}`
      : typed;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: displayContent,
    };
    setMessages((prev) => [...prev, userMessage]);
    setDraft("");
    setAttachment(null);
    setStatus({ tone: "busy", text: "Thinking" });
    setAvatarState("thinking");
    setAvatarEmotion("focused");

    try {
      const response = await sendChat(
        sentContent,
        sessionId,
        personalityId,
        selectedProvider,
        selectedAgent || null,
        { skillId: activeSkill?.id ?? null, webSearch: webSearchOn },
      );
      setSessionId(response.session_id);
      setActiveSkill(null); // one-shot: skill applies to this message only
      setAvatarEmotion(normalizeEmotion(response.emotion));
      setMessages((current) => [
        ...current,
        {
          id: response.message_id,
          role: "assistant",
          content: response.text,
          artifacts: response.artifacts,
          citations: response.citations,
          tool_trace: response.tool_trace,
          tool_requests: response.tool_requests,
          agent_run_id: response.agent_run_id,
        },
      ]);

      // `speechOutputEnabled` is the single source of truth for whether this
      // reply gets spoken. It tracks the persisted `auto_speak` preference
      // (see the effect above) until the user deliberately taps the composer
      // button, at which point that tap wins over later settings refreshes —
      // so the button's label/icon and actual speak-or-not behavior always
      // agree, in both directions.
      if (speechOutputEnabled) {
        setAvatarState("speaking");
        speakText(response.text, voiceSettingsFromValues(appSettings), () =>
          setAvatarState("idle"),
        );
      } else {
        setAvatarState(
          response.memory_candidates.length > 0 ? "confirming" : "idle",
        );
      }

      await Promise.all([refreshMemory(), refreshSessions()]);
      setStatus({
        tone: "ok",
        text:
          response.memory_candidates.length > 0
            ? "Memory candidate captured"
            : "Response received",
      });
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Request failed",
      });
      setAvatarState("error");
      setAvatarEmotion("concerned");
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void send(draft);
  }

  function handleNewChat() {
    stopSpeaking();
    setMessages([]);
    setSessionId(null);
    setDraft("");
    setStatus({ tone: "idle", text: "Ready" });
    setAvatarState("idle");
    setAvatarEmotion("neutral");
    setMemoryOpen(false);
  }

  async function handleDeleteAllSessions() {
    setStatus({ tone: "busy", text: "Clearing sessions" });
    try {
      const report = await deleteAllSessions();
      // The rows are gone server-side; every view that was reading them has to
      // be brought back in line, or the UI keeps showing deleted data.
      await refreshSessions();
      // Whatever conversation was open no longer exists — reset to a new chat
      // rather than leave a transcript on screen with no row behind it.
      stopSpeaking();
      setMessages([]);
      setSessionId(null);
      setDraft("");
      setAvatarState("idle");
      setAvatarEmotion("neutral");
      // Clearing sessions cascades to memory *candidates* that were pending on
      // them. Without this the drawer keeps offering candidates whose source
      // conversation is gone, and approving one would fail.
      await refreshMemory();
      setStatus({
        tone: "ok",
        text: `Cleared ${report.deleted_sessions} sessions, ${report.deleted_messages} messages`,
      });
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Clear failed",
      });
    }
  }

  async function handleOpenSession(id: string) {
    setStatus({ tone: "busy", text: "Loading conversation" });
    try {
      const history = await fetchSessionMessages(id);
      setMessages(
        history.map((row) => ({
          id: row.id,
          role: row.role,
          content: row.content,
        })),
      );
      setSessionId(id);
      setMemoryOpen(false);
      setStatus({ tone: "ok", text: "Conversation loaded" });
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Load failed",
      });
    }
  }

  function handleListen() {
    if (isListening) {
      recognizerRef.current?.stop();
      setIsListening(false);
      setStatus({ tone: "idle", text: "Stopped listening" });
      setAvatarState("idle");
      return;
    }

    const recognizer = createSpeechRecognizer(
      (text) => {
        if (text) {
          setDraft((current) => (current ? `${current} ${text}` : text));
          setStatus({ tone: "ok", text: "Transcript ready" });
          setAvatarEmotion("focused");
        }
      },
      (message) => {
        setStatus({ tone: "error", text: `Speech input: ${message}` });
        setIsListening(false);
        setAvatarState("error");
        setAvatarEmotion("concerned");
      },
      () => setIsListening(false),
      voiceSettingsFromValues(appSettings),
    );

    if (!recognizer) {
      setStatus({ tone: "error", text: "Speech input unavailable" });
      setAvatarState("warning");
      return;
    }

    recognizerRef.current = recognizer;
    setIsListening(true);
    setStatus({ tone: "busy", text: "Listening" });
    setAvatarState("listening");
    setAvatarEmotion("calm");
    recognizer.start();
  }

  function handleSpeechOutputToggle() {
    speechOutputTappedRef.current = true;
    if (speechOutputEnabled) {
      stopSpeaking();
      setSpeechOutputEnabled(false);
      setStatus({ tone: "idle", text: "Speech output off" });
      return;
    }
    setSpeechOutputEnabled(true);
    setStatus({ tone: "ok", text: "Speech output on" });
  }

  async function handleCandidateSave(candidate: MemoryCandidate) {
    setStatus({ tone: "busy", text: "Saving candidate" });
    try {
      await updateMemoryCandidate(candidate);
      await refreshMemory();
      setStatus({ tone: "ok", text: "Candidate saved" });
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Save failed",
      });
    }
  }

  async function handleCandidateDecision(id: string, action: "approve" | "reject") {
    setStatus({
      tone: "busy",
      text: action === "approve" ? "Approving memory" : "Rejecting memory",
    });
    try {
      if (action === "approve") {
        await approveMemoryCandidate(id);
      } else {
        await rejectMemoryCandidate(id);
      }
      await refreshMemory();
      setStatus({
        tone: "ok",
        text: action === "approve" ? "Memory approved" : "Candidate rejected",
      });
      setAvatarEmotion(action === "approve" ? "happy" : "calm");
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Action failed",
      });
    }
  }

  async function handleMemorySave(memory: Memory) {
    setStatus({ tone: "busy", text: "Saving memory" });
    try {
      await updateMemory(memory);
      await refreshMemory();
      setStatus({ tone: "ok", text: "Memory saved" });
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Save failed",
      });
    }
  }

  async function handleMemoryDelete(id: string) {
    setStatus({ tone: "busy", text: "Deleting memory" });
    try {
      await deleteMemory(id);
      await refreshMemory();
      setStatus({ tone: "ok", text: "Memory deleted" });
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Delete failed",
      });
    }
  }

  async function handlePatchSettings(
    changes: Record<string, string | number | boolean>,
  ) {
    try {
      const next = await patchSettings(changes);
      setAppSettings(next);
      setSettingsError(null);
    } catch (error) {
      const text = error instanceof Error ? error.message : "Settings failed";
      setStatus({ tone: "error", text });
      // Also surface it *inside* the dialog. The status pill lives in
      // WorkspaceHeader, which the settings scrim covers and blurs
      // (`fixed inset-0 ... backdrop-blur-sm z-50`), so with Settings open a
      // failed write was previously reported only somewhere the user cannot
      // read. Deliberately not a rethrow: two of the three call sites below
      // invoke this without awaiting, and rejecting would make those
      // unhandled.
      setSettingsError(text);
    }
  }

  async function refreshKnowledge() {
    try {
      setKnowledge(await fetchKnowledge());
    } catch {
      /* knowledge base is optional */
    }
  }

  async function handleReindex(full: boolean, source?: string) {
    setStatus({ tone: "busy", text: full ? "Rebuilding knowledge" : "Reindexing knowledge" });
    try {
      const report = await reindexKnowledge(full, source);
      await refreshKnowledge();
      setStatus({
        tone: "ok",
        text: `Indexed ${report.indexed}, skipped ${report.skipped}, removed ${report.removed}`,
      });
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Reindex failed",
      });
    }
  }

  async function handleConnectGDrive() {
    setStatus({ tone: "busy", text: "Opening Google consent…" });
    try {
      await connectGDrive();
      await refreshKnowledge();
      setStatus({ tone: "ok", text: "Google Drive connected" });
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Connect failed",
      });
    }
  }

  async function handleDisconnectGDrive() {
    try {
      await disconnectGDrive();
      await refreshKnowledge();
      setStatus({ tone: "ok", text: "Google Drive disconnected" });
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Disconnect failed",
      });
    }
  }

  async function handleToolDecision(
    runId: string,
    toolCallId: string,
    approved: boolean,
  ) {
    setDecisionBusy(true);
    setStatus({ tone: "busy", text: approved ? "Running tool" : "Skipping tool" });
    try {
      const result = await resumeAgentRun(runId, toolCallId, approved);
      setMessages((current) => [
        // clear the approval card on the message that raised it
        ...current.map((m) =>
          m.agent_run_id === runId ? { ...m, tool_requests: [] } : m,
        ),
        {
          id: crypto.randomUUID(),
          role: "assistant" as const,
          content: result.text,
          artifacts: result.artifacts,
          citations: result.citations,
          tool_trace: result.tool_trace,
          tool_requests: result.tool_requests,
          agent_run_id: result.agent_run_id,
        },
      ]);
      setStatus({ tone: "ok", text: "Response received" });
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Resume failed",
      });
    } finally {
      setDecisionBusy(false);
    }
  }

  const devMode = appSettings?.values.ui_mode === "developer";
  const webSearchAvailable = Boolean(appSettings?.values.web_search_enabled);
  const canvasEnabled = appSettings?.values.canvas_enabled !== false;
  const sessionArtifacts = useMemo(
    () => messages.flatMap((message) => message.artifacts ?? []),
    [messages],
  );

  function openArtifact(id: string) {
    setCanvasArtifactId(id);
    setCanvasOpen(true);
  }

  // Every entry point into Settings goes through here so a write failure from
  // a previous visit is never still on screen when the dialog reopens.
  function openSettings() {
    setSettingsError(null);
    setSettingsOpen(true);
  }

  const composerProps = {
    value: draft,
    onChange: setDraft,
    onSubmit: handleSubmit,
    canSend,
    speechInputAvailable,
    isListening,
    onToggleListen: handleListen,
    speechOutputAvailable,
    speechOutputEnabled,
    onToggleSpeechOutput: handleSpeechOutputToggle,
    providerLabel: shortProviderLabel(selectedProvider),
    onOpenSettings: openSettings,
    assistantName,
    onAttach: handleAttach,
    attaching,
    attachment: attachment
      ? { filename: attachment.filename, ocr: attachment.ocr }
      : null,
    onRemoveAttachment: () => setAttachment(null),
    activeSkill,
    onPickSkill: setActiveSkill,
    webSearchAvailable,
    webSearchOn: webSearchOn && webSearchAvailable,
    onToggleWebSearch: () => setWebSearchOn((value) => !value),
  };

  return (
    <div className="flex h-full w-full overflow-hidden">
      <Sidebar
        expanded={sidebarExpanded}
        onToggle={() => setSidebarExpanded((value) => !value)}
        onNewChat={handleNewChat}
        sessions={sessions}
        activeSessionId={sessionId}
        onOpenSession={handleOpenSession}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onOpenSettings={openSettings}
        providerActive={selectedProvider === "mock" || providers.length > 0}
        assistantName={assistantName}
      />

      <main className="flex-1 bg-navy-950 flex flex-col overflow-hidden relative">
        <WorkspaceHeader
          sessionLabel={sessionLabel}
          status={status}
          agentName={agents.find((a) => a.id === selectedAgent)?.name ?? null}
        />

        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto custom-scrollbar px-4 md:px-8 py-6 flex flex-col"
        >
          {isNewChat ? (
            <EmptyState
              assistantName={assistantName}
              onQuickPrompt={(text) => void send(text)}
              composer={<Composer {...composerProps} variant="hero" />}
            />
          ) : (
            <ChatTimeline
              messages={messages}
              typing={status.tone === "busy" && status.text === "Thinking"}
              assistantName={assistantName}
              onOpenArtifact={canvasEnabled ? openArtifact : undefined}
              onToolDecision={handleToolDecision}
              decisionBusy={decisionBusy}
            />
          )}
        </div>

        {!isNewChat && (
          <footer className="p-6 shrink-0 bg-gradient-to-t from-navy-950 via-navy-950/90 to-transparent">
            <Composer {...composerProps} variant="footer" />
          </footer>
        )}

        <VoiceOverlay open={isListening} name={assistantName} onStop={handleListen} />
      </main>

      {canvasOpen && canvasEnabled && (
        <CanvasPanel
          artifacts={sessionArtifacts}
          activeId={canvasArtifactId}
          onSelect={setCanvasArtifactId}
          onClose={() => setCanvasOpen(false)}
        />
      )}

      <AvatarPresence
        name={assistantName}
        state={avatarState}
        emotion={avatarEmotion}
        visible={!isNewChat && !isListening}
      />

      <FloatingTools
        visible={!isListening}
        pendingCount={candidates.length}
        onToggleMemory={() => setMemoryOpen((value) => !value)}
        onOpenSettings={openSettings}
        onOpenHelp={() => setHelpOpen(true)}
        onOpenSkillLab={() => setSkillLabOpen(true)}
        devMode={devMode}
      />

      <MemoryDrawer
        open={memoryOpen}
        onClose={() => setMemoryOpen(false)}
        candidates={candidates}
        memories={memories}
        info={memoryInfo}
        onRefresh={() => void refreshMemory()}
        onCandidateChange={(next) =>
          setCandidates((current) =>
            current.map((item) => (item.id === next.id ? next : item)),
          )
        }
        onCandidateSave={handleCandidateSave}
        onCandidateDecision={handleCandidateDecision}
        onMemoryChange={(next) =>
          setMemories((current) =>
            current.map((item) => (item.id === next.id ? next : item)),
          )
        }
        onMemorySave={handleMemorySave}
        onMemoryDelete={handleMemoryDelete}
      />

      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        personalities={personalities}
        personalityId={personalityId}
        onSelectPersonality={(id) => {
          setPersonalityId(id);
          // patchNow, not patchDebounced: this is a click-driven control that
          // renders straight from `personalityId`/`values`, not local state
          // accumulating a stream of changes — see the `patchNow` vs
          // `patchDebounced` note on `PanelProps` in SettingsShell.tsx.
          handlePatchSettings({ default_personality: id });
        }}
        providers={providers}
        selectedProvider={selectedProvider}
        onSelectProvider={(id) => {
          setSelectedProvider(id);
          handlePatchSettings({ default_provider: id });
        }}
        router={routerInfo}
        agents={agents}
        selectedAgent={selectedAgent}
        onSelectAgent={setSelectedAgent}
        skills={skills}
        settings={appSettings}
        onPatchSettings={handlePatchSettings}
        patchError={settingsError}
        onSettingsReset={(next) => {
          setAppSettings(next);
          // One-shot resync, on this one event — deliberately NOT a recurring
          // effect keyed on `[appSettings]`. A group reset clears
          // `default_personality` / `default_provider` server-side; without
          // this the open picker keeps showing the pre-reset selection while
          // the section's "modified" dot has already cleared, and the session
          // keeps *sending* the pre-reset persona and provider on
          // `/api/chat` until reload. A recurring resync instead would
          // re-apply a stale stored id after any unrelated PATCH, because the
          // bootstrap correction above is deliberately not written back to
          // the server. Resets of other groups leave these keys untouched, so
          // `resolveOffered` returns `current` and this is a no-op there.
          setPersonalityId((current) =>
            resolveOffered(
              String(next.values.default_personality ?? ""),
              current,
              personalities,
              "",
            ),
          );
          setSelectedProvider((current) =>
            resolveOffered(
              String(next.values.default_provider ?? ""),
              current,
              providers,
              activeProviderRef.current,
            ),
          );
        }}
        onOpenSkillLab={() => {
          setSettingsOpen(false);
          setSkillLabOpen(true);
        }}
        knowledge={knowledge}
        onReindex={handleReindex}
        onConnectGDrive={handleConnectGDrive}
        onDisconnectGDrive={handleDisconnectGDrive}
        devMode={devMode}
        onDeleteAllSessions={handleDeleteAllSessions}
      />

      <HelpModal
        open={helpOpen}
        onClose={() => setHelpOpen(false)}
        assistantName={assistantName}
      />

      <SkillLab open={skillLabOpen} onClose={() => setSkillLabOpen(false)} />
    </div>
  );
}
