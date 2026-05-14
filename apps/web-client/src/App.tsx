import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  Check,
  Database,
  Mic,
  RefreshCw,
  Save,
  Send,
  Square,
  Trash2,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { AvatarPanel } from "./components/AvatarPanel";
import {
  ChatMessage,
  Memory,
  MemoryCandidate,
  PersonalityProfile,
  apiBaseUrl,
  approveMemoryCandidate,
  deleteMemory,
  fetchMemories,
  fetchMemoryCandidates,
  fetchPersonalities,
  rejectMemoryCandidate,
  sendChat,
  updateMemory,
  updateMemoryCandidate,
} from "./lib/api";
import {
  canRecognizeSpeech,
  canSpeak,
  createSpeechRecognizer,
  speakText,
  stopSpeaking,
} from "./lib/speech";
import {
  AvatarEmotion,
  AvatarState,
  normalizeEmotion,
} from "./lib/avatar";

type Status = {
  tone: "idle" | "busy" | "ok" | "error";
  text: string;
};

export function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [speechOutputEnabled, setSpeechOutputEnabled] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [avatarState, setAvatarState] = useState<AvatarState>("idle");
  const [avatarEmotion, setAvatarEmotion] = useState<AvatarEmotion>("neutral");
  const [status, setStatus] = useState<Status>({
    tone: "idle",
    text: "Ready",
  });
  const [personalities, setPersonalities] = useState<PersonalityProfile[]>([]);
  const [personalityId, setPersonalityId] = useState("violet.default");
  const [candidates, setCandidates] = useState<MemoryCandidate[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const recognizerRef = useRef<ReturnType<typeof createSpeechRecognizer>>(null);

  const canSend = draft.trim().length > 0 && status.tone !== "busy";
  const speechInputAvailable = canRecognizeSpeech();
  const speechOutputAvailable = canSpeak();

  async function refreshMemory() {
    const [nextCandidates, nextMemories] = await Promise.all([
      fetchMemoryCandidates(),
      fetchMemories(),
    ]);
    setCandidates(nextCandidates);
    setMemories(nextMemories);
  }

  useEffect(() => {
    Promise.all([refreshMemory(), fetchPersonalities()])
      .then(([, nextPersonalities]) => {
        setPersonalities(nextPersonalities);
        if (
          nextPersonalities.length > 0 &&
          !nextPersonalities.some((profile) => profile.id === personalityId)
        ) {
          setPersonalityId(nextPersonalities[0].id);
        }
      })
      .catch((error: Error) => {
        setStatus({ tone: "error", text: error.message });
      });
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (!content) {
      return;
    }

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
    };
    setMessages((current) => [...current, userMessage]);
    setDraft("");
    setStatus({ tone: "busy", text: "Thinking" });
    setAvatarState("thinking");
    setAvatarEmotion("focused");

    try {
      const response = await sendChat(content, sessionId, personalityId);
      const nextEmotion = normalizeEmotion(response.emotion);
      setSessionId(response.session_id);
      setAvatarEmotion(nextEmotion);
      setMessages((current) => [
        ...current,
        {
          id: response.message_id,
          role: "assistant",
          content: response.text,
        },
      ]);
      if (speechOutputEnabled) {
        setAvatarState("speaking");
        speakText(response.text, () => {
          setAvatarState("idle");
        });
      } else {
        setAvatarState(
          response.memory_candidates.length > 0 ? "confirming" : "idle",
        );
      }
      await refreshMemory();
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
          setAvatarState("confirming");
          setAvatarEmotion("focused");
        }
      },
      (message) => {
        setStatus({ tone: "error", text: `Speech input: ${message}` });
        setIsListening(false);
        setAvatarState("error");
        setAvatarEmotion("concerned");
      },
      () => {
        setIsListening(false);
      },
    );

    if (!recognizer) {
      setStatus({ tone: "error", text: "Speech input unavailable" });
      setAvatarState("warning");
      setAvatarEmotion("concerned");
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
      setAvatarState("idle");
      return;
    }
    setSpeechOutputEnabled(true);
    setStatus({ tone: "ok", text: "Speech output on" });
    setAvatarState("confirming");
    setAvatarEmotion("happy");
  }

  async function handleCandidateSave(candidate: MemoryCandidate) {
    setStatus({ tone: "busy", text: "Saving candidate" });
    setAvatarState("thinking");
    try {
      await updateMemoryCandidate(candidate);
      await refreshMemory();
      setStatus({ tone: "ok", text: "Candidate saved" });
      setAvatarState("confirming");
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Save failed",
      });
      setAvatarState("error");
      setAvatarEmotion("concerned");
    }
  }

  async function handleCandidateDecision(
    id: string,
    action: "approve" | "reject",
  ) {
    setStatus({
      tone: "busy",
      text: action === "approve" ? "Approving memory" : "Rejecting memory",
    });
    setAvatarState("thinking");
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
      setAvatarState("confirming");
      setAvatarEmotion(action === "approve" ? "happy" : "calm");
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Action failed",
      });
      setAvatarState("error");
      setAvatarEmotion("concerned");
    }
  }

  async function handleMemorySave(memory: Memory) {
    setStatus({ tone: "busy", text: "Saving memory" });
    setAvatarState("thinking");
    try {
      await updateMemory(memory);
      await refreshMemory();
      setStatus({ tone: "ok", text: "Memory saved" });
      setAvatarState("confirming");
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Save failed",
      });
      setAvatarState("error");
      setAvatarEmotion("concerned");
    }
  }

  async function handleMemoryDelete(id: string) {
    setStatus({ tone: "busy", text: "Deleting memory" });
    setAvatarState("warning");
    try {
      await deleteMemory(id);
      await refreshMemory();
      setStatus({ tone: "ok", text: "Memory deleted" });
      setAvatarState("confirming");
      setAvatarEmotion("calm");
    } catch (error) {
      setStatus({
        tone: "error",
        text: error instanceof Error ? error.message : "Delete failed",
      });
      setAvatarState("error");
      setAvatarEmotion("concerned");
    }
  }

  const sessionLabel = useMemo(() => {
    if (!sessionId) {
      return "New session";
    }
    return sessionId.slice(0, 8);
  }, [sessionId]);

  return (
    <main className="app-shell">
      <AvatarPanel
        state={avatarState}
        emotion={avatarEmotion}
        speechInputAvailable={speechInputAvailable}
        speechOutputEnabled={speechOutputEnabled}
      />

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>Violet</h1>
            <p>{sessionLabel}</p>
          </div>
          <label className="persona-select">
            <span>Persona</span>
            <select
              value={personalityId}
              onChange={(event) => setPersonalityId(event.target.value)}
            >
              {personalities.length === 0 ? (
                <option value="violet.default">Violet Default</option>
              ) : (
                personalities.map((profile) => (
                  <option value={profile.id} key={profile.id}>
                    {profile.id === "violet.devoted_strategist"
                      ? "Devoted Strategist"
                      : profile.name}
                  </option>
                ))
              )}
            </select>
          </label>
          <div className={`status ${status.tone}`}>{status.text}</div>
        </header>

        <section className="chat-log" aria-label="Chat messages">
          {messages.length === 0 ? (
            <div className="empty-state">Violet is ready on {apiBaseUrl}</div>
          ) : (
            messages.map((message) => (
              <article className={`message ${message.role}`} key={message.id}>
                <span>{message.role === "assistant" ? "Violet" : "You"}</span>
                <p>{message.content}</p>
              </article>
            ))
          )}
        </section>

        <form className="composer" onSubmit={handleSubmit}>
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Message Violet"
            rows={3}
          />
          <div className="composer-actions">
            <button
              type="button"
              disabled={!speechInputAvailable}
              onClick={handleListen}
              title={isListening ? "Stop listening" : "Start speech input"}
            >
              {isListening ? <Square size={17} /> : <Mic size={18} />}
            </button>
            <button
              type="button"
              disabled={!speechOutputAvailable}
              onClick={handleSpeechOutputToggle}
              title={
                speechOutputEnabled
                  ? "Disable speech output"
                  : "Enable speech output"
              }
            >
              {speechOutputEnabled ? <Volume2 size={18} /> : <VolumeX size={18} />}
            </button>
            <button type="submit" disabled={!canSend} title="Send">
              <Send size={18} />
            </button>
          </div>
        </form>
      </section>

      <aside className="memory-panel">
        <div className="panel-header">
          <div>
            <h2>Memory</h2>
            <p>{candidates.length} pending</p>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={() => refreshMemory()}
            title="Refresh"
          >
            <RefreshCw size={17} />
          </button>
        </div>

        <MemorySection
          title="Candidates"
          icon={<Database size={16} />}
          empty="No pending candidates"
        >
          {candidates.map((candidate) => (
            <CandidateCard
              candidate={candidate}
              key={candidate.id}
              onChange={(next) =>
                setCandidates((current) =>
                  current.map((item) => (item.id === next.id ? next : item)),
                )
              }
              onSave={handleCandidateSave}
              onApprove={(id) => handleCandidateDecision(id, "approve")}
              onReject={(id) => handleCandidateDecision(id, "reject")}
            />
          ))}
        </MemorySection>

        <MemorySection
          title="Approved"
          icon={<Check size={16} />}
          empty="No approved memories"
        >
          {memories.map((memory) => (
            <MemoryCard
              key={memory.id}
              memory={memory}
              onChange={(next) =>
                setMemories((current) =>
                  current.map((item) => (item.id === next.id ? next : item)),
                )
              }
              onSave={handleMemorySave}
              onDelete={handleMemoryDelete}
            />
          ))}
        </MemorySection>
      </aside>
    </main>
  );
}

function MemorySection({
  title,
  icon,
  empty,
  children,
}: {
  title: string;
  icon: ReactNode;
  empty: string;
  children: ReactNode;
}) {
  const isEmpty = Array.isArray(children) && children.length === 0;
  return (
    <section className="memory-section">
      <h3>
        {icon}
        {title}
      </h3>
      {isEmpty ? <div className="empty-memory">{empty}</div> : children}
    </section>
  );
}

function CandidateCard({
  candidate,
  onChange,
  onSave,
  onApprove,
  onReject,
}: {
  candidate: MemoryCandidate;
  onChange: (candidate: MemoryCandidate) => void;
  onSave: (candidate: MemoryCandidate) => void;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}) {
  return (
    <article className="memory-card">
      <div className="memory-meta">
        <input
          value={candidate.memory_type}
          onChange={(event) =>
            onChange({ ...candidate, memory_type: event.target.value })
          }
          aria-label="Candidate type"
        />
        <span>{Math.round(candidate.confidence * 100)}%</span>
      </div>
      <textarea
        value={candidate.content}
        onChange={(event) =>
          onChange({ ...candidate, content: event.target.value })
        }
        rows={3}
        aria-label="Candidate content"
      />
      <p>{candidate.reason}</p>
      <div className="card-actions">
        <button type="button" onClick={() => onSave(candidate)} title="Save">
          <Save size={16} />
        </button>
        <button
          type="button"
          onClick={() => onApprove(candidate.id)}
          title="Approve"
        >
          <Check size={16} />
        </button>
        <button
          type="button"
          onClick={() => onReject(candidate.id)}
          title="Reject"
        >
          <X size={16} />
        </button>
      </div>
    </article>
  );
}

function MemoryCard({
  memory,
  onChange,
  onSave,
  onDelete,
}: {
  memory: Memory;
  onChange: (memory: Memory) => void;
  onSave: (memory: Memory) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <article className="memory-card approved">
      <div className="memory-meta">
        <input
          value={memory.memory_type}
          onChange={(event) =>
            onChange({ ...memory, memory_type: event.target.value })
          }
          aria-label="Memory type"
        />
        <span>{Math.round(memory.confidence * 100)}%</span>
      </div>
      <textarea
        value={memory.content}
        onChange={(event) => onChange({ ...memory, content: event.target.value })}
        rows={3}
        aria-label="Memory content"
      />
      <div className="card-actions">
        <button type="button" onClick={() => onSave(memory)} title="Save">
          <Save size={16} />
        </button>
        <button type="button" onClick={() => onDelete(memory.id)} title="Delete">
          <Trash2 size={16} />
        </button>
      </div>
    </article>
  );
}
