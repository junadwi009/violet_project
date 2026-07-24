import { Check, Save, Trash2, X, Database, RefreshCw, FolderOpen, HardDrive } from "lucide-react";
import { Memory, MemoryCandidate, MemoryInfo } from "../lib/api";

type MemoryDrawerProps = {
  open: boolean;
  onClose: () => void;
  candidates: MemoryCandidate[];
  memories: Memory[];
  info: MemoryInfo | null;
  onRefresh: () => void;
  onCandidateChange: (candidate: MemoryCandidate) => void;
  onCandidateSave: (candidate: MemoryCandidate) => void;
  onCandidateDecision: (id: string, action: "approve" | "reject") => void;
  onMemoryChange: (memory: Memory) => void;
  onMemorySave: (memory: Memory) => void;
  onMemoryDelete: (id: string) => void;
};

export function MemoryDrawer(props: MemoryDrawerProps) {
  const { open, onClose, candidates, memories, info, onRefresh } = props;
  return (
    <>
      <div
        className={`fixed inset-0 bg-steel-dark/20 backdrop-blur-sm z-40 transition-opacity duration-300 ${
          open ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
        onClick={onClose}
      />
      <aside
        className={`fixed top-0 right-0 h-full w-[380px] max-w-[92vw] bg-navy-900 border-l border-navy-700/40 z-50 shadow-2xl flex flex-col transition-transform duration-300 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-6 py-5 border-b border-navy-700/30">
          <div>
            <h2 className="text-xl font-semibold text-steel-dark flex items-center gap-2">
              <Database size={18} className="text-steel-highlight" />
              Memory
            </h2>
            <p className="text-xs text-steel/70 mt-0.5">
              {candidates.length} pending · {memories.length} approved
            </p>
            {info && (
              <p
                className="text-[10px] text-steel/60 mt-1 flex items-center gap-1 max-w-[240px] truncate"
                title={info.location}
              >
                {info.backend === "files" ? (
                  <FolderOpen size={11} className="shrink-0 text-steel-highlight" />
                ) : (
                  <HardDrive size={11} className="shrink-0" />
                )}
                <span className="truncate">
                  {info.backend} · {info.location}
                </span>
              </p>
            )}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={onRefresh}
              className="w-9 h-9 rounded-lg flex items-center justify-center text-steel hover:bg-white/60 transition"
              title="Refresh"
            >
              <RefreshCw size={16} />
            </button>
            <button
              onClick={onClose}
              className="w-9 h-9 rounded-lg flex items-center justify-center text-steel hover:bg-white/60 transition"
              title="Close"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar px-5 py-5 space-y-6">
          <Section title="Candidates" empty="No pending candidates">
            {candidates.map((candidate) => (
              <CandidateCard
                key={candidate.id}
                candidate={candidate}
                onChange={props.onCandidateChange}
                onSave={props.onCandidateSave}
                onApprove={(id) => props.onCandidateDecision(id, "approve")}
                onReject={(id) => props.onCandidateDecision(id, "reject")}
              />
            ))}
          </Section>

          <Section title="Approved" empty="No approved memories">
            {memories.map((memory) => (
              <MemoryCard
                key={memory.id}
                memory={memory}
                onChange={props.onMemoryChange}
                onSave={props.onMemorySave}
                onDelete={props.onMemoryDelete}
              />
            ))}
          </Section>
        </div>
      </aside>
    </>
  );
}

function Section({
  title,
  empty,
  children,
}: {
  title: string;
  empty: string;
  children: React.ReactNode;
}) {
  const isEmpty = Array.isArray(children) && children.length === 0;
  return (
    <section className="space-y-3">
      <h3 className="text-xs font-bold text-steel/60 uppercase tracking-widest">
        {title}
      </h3>
      {isEmpty ? (
        <div className="p-4 rounded-xl border border-dashed border-navy-700/40 text-sm text-steel/60">
          {empty}
        </div>
      ) : (
        children
      )}
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
    <article className="bg-white border border-navy-700/30 rounded-xl p-3 space-y-2.5 shadow-sm">
      <div className="flex items-center gap-2">
        <input
          value={candidate.memory_type}
          onChange={(e) => onChange({ ...candidate, memory_type: e.target.value })}
          aria-label="Candidate type"
          className="flex-1 h-8 px-2.5 rounded-lg bg-steel-ice border border-navy-700/20 text-xs text-steel-dark focus:outline-none focus:border-steel-highlight/50"
        />
        <span className="text-xs text-steel/70 font-mono">
          {Math.round(candidate.confidence * 100)}%
        </span>
      </div>
      <textarea
        value={candidate.content}
        onChange={(e) => onChange({ ...candidate, content: e.target.value })}
        rows={3}
        aria-label="Candidate content"
        className="w-full rounded-lg bg-steel-ice border border-navy-700/20 p-2.5 text-sm text-steel-dark resize-y focus:outline-none focus:border-steel-highlight/50"
      />
      <p className="text-xs text-steel/70">{candidate.reason}</p>
      <div className="flex justify-end gap-2">
        <IconBtn onClick={() => onSave(candidate)} title="Save" tone="neutral">
          <Save size={15} />
        </IconBtn>
        <IconBtn onClick={() => onApprove(candidate.id)} title="Approve" tone="approve">
          <Check size={15} />
        </IconBtn>
        <IconBtn onClick={() => onReject(candidate.id)} title="Reject" tone="reject">
          <X size={15} />
        </IconBtn>
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
    <article className="bg-white border border-steel-highlight/25 rounded-xl p-3 space-y-2.5 shadow-sm">
      <div className="flex items-center gap-2">
        <input
          value={memory.memory_type}
          onChange={(e) => onChange({ ...memory, memory_type: e.target.value })}
          aria-label="Memory type"
          className="flex-1 h-8 px-2.5 rounded-lg bg-steel-ice border border-navy-700/20 text-xs text-steel-dark focus:outline-none focus:border-steel-highlight/50"
        />
        <span className="text-xs text-steel/70 font-mono">
          {Math.round(memory.confidence * 100)}%
        </span>
      </div>
      <textarea
        value={memory.content}
        onChange={(e) => onChange({ ...memory, content: e.target.value })}
        rows={3}
        aria-label="Memory content"
        className="w-full rounded-lg bg-steel-ice border border-navy-700/20 p-2.5 text-sm text-steel-dark resize-y focus:outline-none focus:border-steel-highlight/50"
      />
      <div className="flex justify-end gap-2">
        <IconBtn onClick={() => onSave(memory)} title="Save" tone="neutral">
          <Save size={15} />
        </IconBtn>
        <IconBtn onClick={() => onDelete(memory.id)} title="Delete" tone="reject">
          <Trash2 size={15} />
        </IconBtn>
      </div>
    </article>
  );
}

function IconBtn({
  children,
  onClick,
  title,
  tone,
}: {
  children: React.ReactNode;
  onClick: () => void;
  title: string;
  tone: "neutral" | "approve" | "reject";
}) {
  const tones = {
    neutral: "bg-steel text-white hover:bg-steel-dark",
    approve: "bg-emerald-600 text-white hover:bg-emerald-700",
    reject: "bg-red-600 text-white hover:bg-red-700",
  };
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`w-9 h-9 rounded-lg flex items-center justify-center transition ${tones[tone]}`}
    >
      {children}
    </button>
  );
}
