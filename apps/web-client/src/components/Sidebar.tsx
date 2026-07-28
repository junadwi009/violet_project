import { useMemo } from "react";
import {
  Menu,
  PenSquare,
  Search,
  Settings,
} from "lucide-react";
import { SessionSummary } from "../lib/api";

type SidebarProps = {
  expanded: boolean;
  onToggle: () => void;
  onNewChat: () => void;
  sessions: SessionSummary[];
  activeSessionId: string | null;
  onOpenSession: (id: string) => void;
  searchQuery: string;
  onSearchChange: (value: string) => void;
  onOpenSettings: () => void;
  providerActive: boolean;
  assistantName: string;
};

export function Sidebar({
  expanded,
  onToggle,
  onNewChat,
  sessions,
  activeSessionId,
  onOpenSession,
  searchQuery,
  onSearchChange,
  onOpenSettings,
  providerActive,
  assistantName,
}: SidebarProps) {
  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter((s) =>
      (s.title ?? "Untitled").toLowerCase().includes(q),
    );
  }, [sessions, searchQuery]);

  return (
    <aside
      className={`bg-navy-900 flex flex-col justify-between py-6 border-r border-navy-700/40 shrink-0 z-40 shadow-sm transition-all duration-500 ${
        expanded ? "w-72 px-5" : "w-16 px-3"
      }`}
    >
      <div className="flex flex-col h-full min-h-0">
        {/* Brand + toggle */}
        <div className="flex items-center justify-between w-full px-1.5 mb-6">
          {expanded && (
            <div className="flex items-center gap-2.5 overflow-hidden">
              {/* Flat accent, not `from-steel-highlight to-[#c77dff]`. The
                  hardcoded light end was a fixed violet that neither the theme
                  nor the accent picker could reach, and a single letter of ink
                  over it only cleared AA for some accents (light amber landed
                  at 3.66:1). A flat `steel-highlight` under `text-navy-950` is
                  the pairing index.css certifies for all ten theme x accent
                  combinations, worst 4.61:1. */}
              <span className="font-mono w-7 h-7 shrink-0 rounded-lg bg-steel-highlight text-navy-950 flex items-center justify-center font-bold shadow-md">
                V
              </span>
              <span className="font-bold text-steel-dark text-lg tracking-tight">
                {assistantName}
              </span>
            </div>
          )}
          <button
            onClick={onToggle}
            className="p-1.5 rounded-lg hover:bg-navy-800/60 transition text-steel shrink-0"
            title="Toggle sidebar"
          >
            <Menu size={18} />
          </button>
        </div>

        {/* New chat */}
        <button
          onClick={onNewChat}
          className={`w-full p-3 rounded-xl bg-navy-800/50 border border-navy-700/20 text-steel-dark hover:bg-navy-800/80 transition flex items-center gap-4 text-sm font-semibold shadow-sm mb-4 ${
            expanded ? "" : "justify-center"
          }`}
          title="New chat"
        >
          <PenSquare size={17} className="text-steel-highlight shrink-0" />
          {expanded && <span>New chat</span>}
        </button>

        {/* Search */}
        {expanded ? (
          <div className="relative mb-2">
            <Search
              size={15}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-steel-muted"
            />
            <input
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search chats"
              className="w-full bg-navy-800/60 border border-navy-700/20 rounded-xl pl-9 pr-3 py-2 text-sm text-steel-dark placeholder-steel-muted focus:outline-none focus:border-steel-highlight/50"
            />
          </div>
        ) : (
          <button
            onClick={onToggle}
            className="w-full p-2.5 rounded-xl text-steel hover:text-steel-dark hover:bg-navy-800/50 transition flex items-center justify-center"
            title="Search chats"
          >
            <Search size={17} />
          </button>
        )}

        {/* Recents */}
        {expanded && (
          <div className="flex-1 flex flex-col mt-4 min-h-0 border-t border-navy-700/30 pt-4">
            <span className="text-[10px] font-bold text-steel-muted uppercase tracking-widest mb-3 px-2">
              Recents
            </span>
            <div className="flex-1 overflow-y-auto space-y-1 custom-scrollbar pr-1">
              {filtered.length === 0 ? (
                <p className="px-2.5 py-1.5 text-xs text-steel-muted">
                  {sessions.length === 0 ? "No conversations yet" : "No matches"}
                </p>
              ) : (
                filtered.map((session) => (
                  <button
                    key={session.id}
                    onClick={() => onOpenSession(session.id)}
                    className={`w-full text-left px-2.5 py-1.5 text-xs rounded-lg truncate block transition ${
                      session.id === activeSessionId
                        ? "bg-navy-800/70 text-steel-dark font-medium"
                        : "text-steel hover:text-steel-dark hover:bg-navy-800/50"
                    }`}
                    title={session.title ?? "Untitled"}
                  >
                    {session.title ?? "Untitled"}
                  </button>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer: status + user */}
      <div className="flex flex-col gap-4 border-t border-navy-700/30 pt-4 shrink-0">
        <div
          className={`flex items-center gap-2.5 py-1 bg-navy-800/40 border border-navy-700/10 rounded-full transition-all ${
            expanded ? "px-3" : "px-1.5 justify-center"
          }`}
        >
          <span
            className={`w-2.5 h-2.5 rounded-full shrink-0 ${
              providerActive ? "bg-[color:var(--color-success)] animate-pulse" : "bg-steel-light"
            }`}
          />
          {expanded && (
            <span className="text-[11px] text-steel font-semibold uppercase tracking-wider">
              {assistantName} online
            </span>
          )}
        </div>

        <div className="flex items-center justify-between w-full px-1">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-full bg-steel-dark text-navy-950 flex items-center justify-center font-bold text-xs shadow-sm shrink-0">
              U
            </div>
            {expanded && (
              <div className="flex flex-col">
                <span className="text-xs font-bold text-steel-dark leading-tight">
                  You
                </span>
                <span className="text-[10px] text-steel-muted leading-none">
                  Local · Workspace
                </span>
              </div>
            )}
          </div>
          {expanded && (
            <button
              onClick={onOpenSettings}
              className="text-steel hover:text-steel-dark transition shrink-0"
              title="Settings"
            >
              <Settings size={16} />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}
