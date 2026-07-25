import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { SkillInfo, fetchSkills } from "../lib/api";

type Props = {
  query: string; // text after the leading "/"
  onPick: (skill: SkillInfo) => void;
  onClose: () => void;
};

export function SkillPalette({ query, onPick, onClose }: Props) {
  const [skills, setSkills] = useState<SkillInfo[]>([]);

  useEffect(() => {
    fetchSkills()
      .then((r) => setSkills(r.enabled ? r.items : []))
      .catch(() => setSkills([]));
  }, []);

  const q = query.toLowerCase();
  const filtered = skills.filter(
    (s) =>
      s.id.toLowerCase().includes(q) ||
      s.name.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q),
  );
  if (filtered.length === 0) return null;

  return (
    <div className="absolute bottom-full mb-2 left-0 w-full max-w-md bg-white border border-navy-700/20 rounded-2xl shadow-xl overflow-hidden z-30">
      <div className="px-3 py-2 text-[10px] uppercase tracking-wider text-steel/60 border-b border-navy-700/10 flex items-center gap-1.5">
        <Sparkles size={11} className="text-steel-highlight" /> Skills
      </div>
      <ul className="max-h-64 overflow-y-auto custom-scrollbar">
        {filtered.map((s) => (
          <li key={s.id}>
            <button
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                onPick(s);
              }}
              className="w-full text-left px-3 py-2 hover:bg-steel-ice transition flex flex-col"
            >
              <span className="text-sm font-medium text-steel-dark">
                /{s.id} · {s.name}
              </span>
              <span className="text-[11px] text-steel/60 truncate">{s.description}</span>
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onMouseDown={(e) => {
          e.preventDefault();
          onClose();
        }}
        className="w-full text-[10px] text-steel/50 py-1.5 hover:bg-steel-ice"
      >
        Esc to dismiss
      </button>
    </div>
  );
}
