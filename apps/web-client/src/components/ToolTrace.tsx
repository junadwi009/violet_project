import { useState } from "react";
import { ChevronDown, ChevronRight, Wrench } from "lucide-react";
import { ToolTraceEntry } from "../lib/api";

export function ToolTrace({ entries }: { entries: ToolTraceEntry[] }) {
  const [open, setOpen] = useState(false);
  if (entries.length === 0) return null;
  const summary = entries.map((e) => e.tool).join(" · ");
  return (
    <div className="mt-1 text-[11px]">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 text-steel-muted hover:text-steel-dark transition"
      >
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        <Wrench size={10} />
        <span>
          {entries.length} tool step{entries.length > 1 ? "s" : ""} · {summary}
        </span>
      </button>
      {open && (
        <ul className="mt-1 space-y-0.5 pl-4 border-l border-navy-700/15">
          {entries.map((e, i) => (
            <li key={i} className="text-steel-muted">
              <span className="font-medium text-steel-dark">{e.tool}</span>
              <span className="text-steel-muted"> ({e.args})</span>
              {" → "}
              <span className={e.status === "error" ? "text-[color:var(--color-danger)]" : "text-steel-muted"}>
                {e.summary}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
