import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  AgentInfo,
  ChatMessage,
  Memory,
  MemoryCandidate,
  MemoryInfo,
  PersonalityProfile,
  ProviderInfo,
  RouterInfo,
  SessionSummary,
  approveMemoryCandidate,
  deleteMemory,
  fetchAgents,
  fetchMemories,
  fetchMemoryCandidates,
  fetchMemoryInfo,
  fetchPersonalities,
  fetchProviders,
  fetchSessionMessages,
  fetchSessions,
  rejectMemoryCandidate,
  sendChat,
  updateMemory,
  updateMemoryCandidate,
  uploadFile,
} from "./lib/api";
import {
  canRecognizeSpeech,
  canSpeak,
  createSpeechRecognizer,
  speakText,
  stopSpeaking,
} from "./lib/speech";
import { AvatarEmotion, AvatarState, normalizeEmotion } from "./lib/avatar";
import { Sidebar } from "./components/Sidebar";
import { WorkspaceHeader } from "./components/WorkspaceHeader";
import { EmptyState } from "./components/EmptyState";
import { ChatTimeline } from "./components/ChatTimeline";
import { Composer } from "./components/Composer";
import { AvatarPresence } from "./components/AvatarPresence";
import { VoiceOverlay } from "./components/VoiceOverlay";
import { FloatingTools } from "./components/FloatingTools";
import { MemoryDrawer } from "./components/MemoryDrawer";
import { SettingsModal } from "./components/SettingsModal";
import { HelpModal } from "./components/HelpModal";
import { SkillLab } from "./components/SkillLab";

type Status = {
  tone: "idle" | "busy" | "ok" | "error";
  text: string;
};

function shortProviderLabel(id: string): string {
  if (id === "mock") return "Mock";
  if (id === "openai_compatible") return "Local";
  return id;
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

  const recognizerRef = useRef<ReturnType<typeof createSpeechRecognizer>>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

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
    Promise.all([
      refreshMemory(),
      fetchPersonalities(),
      fetchProviders(),
      fetchSessions(),
    ])
      .then(([, nextPersonalities, providerResponse, nextSessions]) => {
        setPersonalities(nextPersonalities);
        if (
          nextPersonalities.length > 0 &&
          !nextPersonalities.some((profile) => profile.id === personalityId)
        ) {
          setPersonalityId(nextPersonalities[0].id);
        }
        setProviders(providerResponse.items);
        setSelectedProvider(providerResponse.active);
        setRouterInfo(providerResponse.router ?? null);
        setSessions(nextSessions);
      })
      .catch((error: Error) => setStatus({ tone: "error", text: error.message }));
    fetchMemoryInfo()
      .then(setMemoryInfo)
      .catch(() => setMemoryInfo(null));
    fetchAgents()
      .then((response) => setAgents(response.enabled ? response.items : []))
      .catch(() => setAgents([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      );
      setSessionId(response.session_id);
      setAvatarEmotion(normalizeEmotion(response.emotion));
      setMessages((current) => [
        ...current,
        {
          id: response.message_id,
          role: "assistant",
          content: response.text,
          artifacts: response.artifacts,
        },
      ]);

      if (speechOutputEnabled) {
        setAvatarState("speaking");
        speakText(response.text, () => setAvatarState("idle"));
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
    onOpenSettings: () => setSettingsOpen(true),
    assistantName,
    onAttach: handleAttach,
    attaching,
    attachment: attachment
      ? { filename: attachment.filename, ocr: attachment.ocr }
      : null,
    onRemoveAttachment: () => setAttachment(null),
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
        onOpenSettings={() => setSettingsOpen(true)}
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
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenHelp={() => setHelpOpen(true)}
        onOpenSkillLab={() => setSkillLabOpen(true)}
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

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        personalities={personalities}
        personalityId={personalityId}
        onSelectPersonality={setPersonalityId}
        providers={providers}
        selectedProvider={selectedProvider}
        onSelectProvider={setSelectedProvider}
        router={routerInfo}
        agents={agents}
        selectedAgent={selectedAgent}
        onSelectAgent={setSelectedAgent}
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
