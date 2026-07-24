type WorkspaceHeaderProps = {
  sessionLabel: string;
  status: { tone: "idle" | "busy" | "ok" | "error"; text: string };
};

const STATUS_STYLES: Record<WorkspaceHeaderProps["status"]["tone"], string> = {
  idle: "bg-steel-ice text-steel border-navy-700/20",
  busy: "bg-amber-50 text-amber-700 border-amber-200",
  ok: "bg-emerald-50 text-emerald-700 border-emerald-200",
  error: "bg-red-50 text-red-700 border-red-200",
};

export function WorkspaceHeader({ sessionLabel, status }: WorkspaceHeaderProps) {
  return (
    <header className="h-16 px-8 flex items-center justify-between border-b border-navy-700/20 shrink-0 bg-white/50 backdrop-blur">
      <div className="flex items-center gap-2">
        <span className="font-semibold text-steel-dark text-sm">
          Violet Workspace
        </span>
        <span className="text-xs text-steel/60">· {sessionLabel}</span>
      </div>
      <div
        className={`text-xs font-medium px-3 py-1.5 rounded-full border max-w-[260px] truncate ${STATUS_STYLES[status.tone]}`}
        title={status.text}
      >
        {status.text}
      </div>
    </header>
  );
}
