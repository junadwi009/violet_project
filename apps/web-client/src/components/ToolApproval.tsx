import { ShieldAlert } from "lucide-react";
import { ToolRequest } from "../lib/api";

type Props = {
  requests: ToolRequest[];
  onDecide: (toolCallId: string, approved: boolean) => void;
  busy: boolean;
};

export function ToolApproval({ requests, onDecide, busy }: Props) {
  if (requests.length === 0) return null;
  return (
    <div className="mt-3 space-y-2">
      {requests.map((r) => (
        <div
          key={r.id}
          // Was `border-amber-300/50 bg-amber-50/60` — literal palette entries,
          // so the whole approval card stayed a pale cream panel on the dark
          // canvas. Same warning-tint shape as the status chips.
          className="rounded-xl border border-[color:var(--color-warning)]/40 bg-[color:var(--color-warning)]/12 p-3 text-xs"
        >
          <div className="flex items-center gap-1.5 font-semibold text-steel-dark">
            <ShieldAlert size={13} className="text-[color:var(--color-warning)]" />
            Approval needed
            <span className="ml-auto text-[10px] uppercase tracking-wider text-[color:var(--color-warning)]">
              {r.risk} risk
            </span>
          </div>
          <p className="mt-1 text-steel-dark">
            Run <span className="font-mono font-semibold">{r.tool}</span>
          </p>
          <pre className="mt-1 overflow-x-auto rounded bg-navy-800/70 p-2 text-[10px] text-steel">
            {JSON.stringify(r.arguments, null, 1)}
          </pre>
          <div className="mt-2 flex gap-2">
            <button
              disabled={busy}
              onClick={() => onDecide(r.id, true)}
              className="flex-1 rounded-lg bg-steel-dark py-1.5 font-semibold text-navy-950 transition hover:opacity-90 disabled:opacity-40"
            >
              Approve
            </button>
            <button
              disabled={busy}
              onClick={() => onDecide(r.id, false)}
              className="flex-1 rounded-lg border border-navy-700/20 bg-navy-800 py-1.5 font-medium text-steel transition disabled:opacity-40"
            >
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
