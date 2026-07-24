import { useEffect, useState } from "react";
import { X, FlaskConical, ShieldCheck, GitMerge, Copy, Loader2 } from "lucide-react";
import {
  CheckResponse,
  LibraryItem,
  checkSkill,
  fetchSkillLibrary,
  mergeSkills,
} from "../lib/api";

type SkillLabProps = {
  open: boolean;
  onClose: () => void;
};

const VERDICT_STYLE: Record<string, string> = {
  keep: "bg-emerald-50 text-emerald-700 border-emerald-200",
  novel: "bg-emerald-50 text-emerald-700 border-emerald-200",
  overlaps: "bg-amber-50 text-amber-700 border-amber-200",
  redundant: "bg-red-50 text-red-700 border-red-200",
  low_quality: "bg-red-50 text-red-700 border-red-200",
};

function Verdict({ verdict }: { verdict: string }) {
  return (
    <span
      className={`text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${
        VERDICT_STYLE[verdict] || "bg-steel-ice text-steel border-navy-700/20"
      }`}
    >
      {verdict}
    </span>
  );
}

export function SkillLab({ open, onClose }: SkillLabProps) {
  const [tab, setTab] = useState<"check" | "merge">("check");
  const [library, setLibrary] = useState<LibraryItem[]>([]);
  const [judgeEnabled, setJudgeEnabled] = useState(false);
  const [status, setStatus] = useState<string>("");

  // check
  const [content, setContent] = useState("");
  const [judge, setJudge] = useState(true);
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<CheckResponse | null>(null);

  // merge
  const [selected, setSelected] = useState<string[]>([]);
  const [mergeName, setMergeName] = useState("");
  const [merging, setMerging] = useState(false);
  const [mergeOut, setMergeOut] = useState("");

  useEffect(() => {
    if (!open) return;
    fetchSkillLibrary()
      .then((r) => {
        setLibrary(r.items);
        setJudgeEnabled(r.judge_enabled);
        setJudge(r.judge_enabled);
      })
      .catch((e: Error) => setStatus(e.message));
  }, [open]);

  if (!open) return null;

  async function runCheck() {
    if (!content.trim()) return;
    setChecking(true);
    setStatus("");
    setResult(null);
    try {
      setResult(await checkSkill(content, judge && judgeEnabled));
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Check failed");
    } finally {
      setChecking(false);
    }
  }

  async function runMerge() {
    if (selected.length < 2 || !mergeName.trim()) return;
    setMerging(true);
    setStatus("");
    setMergeOut("");
    try {
      const r = await mergeSkills(selected, mergeName.trim());
      setMergeOut(r.skill_md);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Merge failed");
    } finally {
      setMerging(false);
    }
  }

  return (
    <div
      className="fixed inset-0 bg-steel-dark/30 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white border border-navy-700/20 rounded-[2rem] w-full max-w-2xl shadow-2xl relative flex flex-col max-h-[88vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-8 pt-7 pb-4 border-b border-navy-700/15">
          <h3 className="text-xl font-semibold text-steel-dark flex items-center gap-2">
            <FlaskConical size={18} className="text-steel-highlight" />
            Skill Lab
          </h3>
          <button onClick={onClose} className="text-steel hover:text-steel-dark" title="Close">
            <X size={18} />
          </button>
        </div>

        <div className="flex gap-1 px-8 pt-4">
          {(["check", "merge"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-t-lg text-sm font-medium flex items-center gap-1.5 transition ${
                tab === t
                  ? "bg-steel-ice text-steel-dark"
                  : "text-steel hover:text-steel-dark"
              }`}
            >
              {t === "check" ? <ShieldCheck size={15} /> : <GitMerge size={15} />}
              {t === "check" ? "Check" : "Merge"}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar px-8 py-5">
          {tab === "check" ? (
            <div className="space-y-3">
              <p className="text-xs text-steel/70">
                Paste a skill (SKILL.md) to vet it against your {library.length} installed
                skills/agents.
              </p>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder={"---\nname: My Skill\ndescription: what it does\n---\nInstructions…"}
                rows={7}
                className="w-full rounded-xl bg-steel-ice border border-navy-700/20 p-3 text-xs font-mono text-steel-dark resize-y focus:outline-none focus:border-steel-highlight/50"
              />
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-1.5 text-xs text-steel">
                  <input
                    type="checkbox"
                    checked={judge}
                    disabled={!judgeEnabled}
                    onChange={(e) => setJudge(e.target.checked)}
                  />
                  LLM judge {judgeEnabled ? "" : "(no key)"}
                </label>
                <button
                  onClick={runCheck}
                  disabled={checking || !content.trim()}
                  className="ml-auto inline-flex items-center gap-1.5 bg-steel-dark hover:bg-black text-white text-sm font-semibold px-4 py-2 rounded-lg transition disabled:opacity-40"
                >
                  {checking ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />}
                  Check
                </button>
              </div>

              {result && (
                <div className="space-y-3 pt-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-steel-dark">
                      {result.candidate.name}
                    </span>
                    <span className="text-[11px] text-steel/60">
                      {result.candidate.triggers.length} triggers · {result.candidate.chars} chars
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-steel-ice border border-navy-700/15 space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-semibold text-steel/60 uppercase">Rule</span>
                      <Verdict verdict={result.rule.verdict} />
                      <span className="text-xs text-steel">{result.rule.reason}</span>
                    </div>
                    {result.llm && result.llm.verdict && (
                      <div className="flex items-start gap-2">
                        <span className="text-[11px] font-semibold text-steel/60 uppercase mt-0.5">LLM</span>
                        <Verdict verdict={result.llm.verdict} />
                        <span className="text-xs text-steel flex-1">{result.llm.reason}</span>
                      </div>
                    )}
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold text-steel/60 uppercase mb-1">
                      Nearest in library
                    </p>
                    <div className="space-y-1">
                      {result.nearest.map((m) => (
                        <div key={m.id} className="flex items-center gap-2 text-xs text-steel">
                          <span className="font-mono text-steel/50 w-12">{m.similarity}</span>
                          <span className="font-medium text-steel-dark">
                            {m.kind}:{m.id}
                          </span>
                          {m.shared_triggers.length > 0 && (
                            <span className="text-[10px] text-steel-highlight">
                              shared: {m.shared_triggers.join(", ")}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-xs text-steel/70">
                Combine 2+ skills/agents into one upgraded SKILL.md.
              </p>
              <div className="max-h-52 overflow-y-auto custom-scrollbar rounded-xl border border-navy-700/15 divide-y divide-navy-700/10">
                {library.map((item) => (
                  <label
                    key={`${item.kind}:${item.id}`}
                    className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-steel-ice/60 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selected.includes(item.id)}
                      onChange={(e) =>
                        setSelected((cur) =>
                          e.target.checked
                            ? [...cur, item.id]
                            : cur.filter((x) => x !== item.id),
                        )
                      }
                    />
                    <span className="font-medium text-steel-dark">{item.name}</span>
                    <span className="text-[10px] text-steel/50 uppercase">{item.kind}</span>
                  </label>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <input
                  value={mergeName}
                  onChange={(e) => setMergeName(e.target.value)}
                  placeholder="New skill name"
                  className="flex-1 rounded-lg bg-steel-ice border border-navy-700/20 px-3 py-2 text-sm text-steel-dark focus:outline-none focus:border-steel-highlight/50"
                />
                <button
                  onClick={runMerge}
                  disabled={merging || selected.length < 2 || !mergeName.trim()}
                  className="inline-flex items-center gap-1.5 bg-steel-dark hover:bg-black text-white text-sm font-semibold px-4 py-2 rounded-lg transition disabled:opacity-40"
                >
                  {merging ? <Loader2 size={15} className="animate-spin" /> : <GitMerge size={15} />}
                  Merge {selected.length > 0 ? `(${selected.length})` : ""}
                </button>
              </div>
              {mergeOut && (
                <div className="relative">
                  <button
                    onClick={() => navigator.clipboard?.writeText(mergeOut)}
                    className="absolute top-2 right-2 inline-flex items-center gap-1 bg-white/80 border border-navy-700/20 rounded-md px-2 py-1 text-[11px] text-steel hover:text-steel-dark"
                  >
                    <Copy size={12} /> Copy
                  </button>
                  <pre className="rounded-xl bg-steel-ice border border-navy-700/20 p-3 text-[11px] font-mono text-steel-dark whitespace-pre-wrap max-h-64 overflow-y-auto custom-scrollbar">
                    {mergeOut}
                  </pre>
                </div>
              )}
            </div>
          )}

          {status && <p className="text-xs text-red-600 mt-3">{status}</p>}
        </div>
      </div>
    </div>
  );
}
