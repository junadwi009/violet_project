type WorkspaceHeaderProps = {
  sessionLabel: string;
  status: { tone: "idle" | "busy" | "ok" | "error"; text: string };
  agentName?: string | null;
};

// Raw palette entries (`amber-50`, `emerald-200`, …) are literals that no theme
// override can reach, so these chips stayed light-mode chips on the dark canvas.
// The 12%-tint / token-text / 40%-border shape is the one documented in
// index.css next to the semantic tokens; ratios there.
const STATUS_STYLES: Record<WorkspaceHeaderProps["status"]["tone"], string> = {
  idle: "bg-steel-ice text-steel border-navy-700/20",
  busy: "bg-[color:var(--color-warning)]/12 text-[color:var(--color-warning)] border-[color:var(--color-warning)]/40",
  ok: "bg-[color:var(--color-success)]/12 text-[color:var(--color-success)] border-[color:var(--color-success)]/40",
  error: "bg-[color:var(--color-danger)]/12 text-[color:var(--color-danger)] border-[color:var(--color-danger)]/40",
};

export function WorkspaceHeader({
  sessionLabel,
  status,
  agentName,
}: WorkspaceHeaderProps) {
  return (
    <header className="h-16 px-8 flex items-center justify-between border-b border-navy-700/20 shrink-0 bg-navy-800/50 backdrop-blur">
      <div className="flex items-center gap-2">
        <span className="font-semibold text-steel-dark text-sm">
          Violet Workspace
        </span>
        <span className="text-xs text-steel-muted">· {sessionLabel}</span>
        {agentName && (
          <span className="ml-1 text-[10px] font-semibold uppercase tracking-wider text-steel-highlight bg-steel-highlight/10 border border-steel-highlight/20 rounded-full px-2 py-0.5">
            ↳ {agentName}
          </span>
        )}
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
