import type { KnowledgeInfo } from "../../../lib/api";
import { SectionHeader } from "../controls/SectionHeader";
import { ToggleRow } from "../controls/ToggleRow";
import type { PanelProps } from "../SettingsShell";

const KNOWLEDGE_KEYS = ["knowledge_auto_sync"];

export function KnowledgePanel({
  values,
  overridden,
  patchNow,
  devMode,
  knowledge,
  onReindex,
  onConnectGDrive,
  onDisconnectGDrive,
  onReset,
}: PanelProps & {
  knowledge: KnowledgeInfo | null;
  onReindex: (full: boolean, source?: string) => void;
  onConnectGDrive: () => void;
  onDisconnectGDrive: () => void;
  onReset: () => void;
}) {
  const modified = KNOWLEDGE_KEYS.some((key) => overridden.includes(key));

  // `/api/knowledge` has not answered, or failed. The old modal rendered
  // nothing at all in this state; a bare header — with a live "Reset
  // section" button for a toggle that is not on screen — is worse than
  // nothing.
  if (!knowledge) return null;

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Knowledge"
        description="Documents Violet can retrieve from while answering."
        modified={modified}
        onReset={onReset}
      />

      <div>
        <label className="block text-xs font-semibold text-steel uppercase tracking-wider mb-2">
          Knowledge base
        </label>
        <div className="p-3 bg-steel-ice rounded-xl border border-navy-700/20 space-y-2">
          <div className="text-[11px] text-steel-dark font-mono truncate">
            {knowledge.dir}
          </div>
          <div className="text-[11px] text-steel">
            {knowledge.doc_count} docs · {knowledge.chunk_count} chunks ·{" "}
            {knowledge.provider}
          </div>
          <ToggleRow
            label="Auto-sync"
            on={values.knowledge_auto_sync === true}
            // Undebounced: this toggle renders `values`, so a debounced
            // write would leave it visibly stuck on the old state for the
            // length of the window.
            onToggle={() =>
              patchNow({
                knowledge_auto_sync: !(values.knowledge_auto_sync === true),
              })
            }
          />
          {knowledge.sources?.map((s) => (
            <div
              key={s.name}
              className="flex items-center gap-2 text-[11px] border-t border-navy-700/10 pt-2"
            >
              <span className="font-medium capitalize text-steel-dark">{s.name}</span>
              <span className={s.connected ? "text-[color:var(--color-success)]" : "text-[color:var(--color-warning)]"}>
                {s.connected ? "connected" : s.detail}
              </span>
              {knowledge.auto_sync?.last_sync?.[s.name]?.at && (
                <span className="text-steel-muted">
                  · synced{" "}
                  {new Date(
                    knowledge.auto_sync.last_sync[s.name]!.at!,
                  ).toLocaleTimeString()}
                </span>
              )}
              {s.name === "gdrive" && !s.connected && s.detail !== "not_configured" && (
                <button
                  onClick={onConnectGDrive}
                  className="ml-auto text-steel-highlight hover:underline"
                >
                  Connect
                </button>
              )}
              {s.name === "gdrive" && s.connected && (
                <span className="ml-auto flex items-center gap-2">
                  <button
                    onClick={() => onReindex(false, "gdrive")}
                    className="text-steel-highlight hover:underline"
                  >
                    Sync
                  </button>
                  {devMode && (
                    <button
                      onClick={onDisconnectGDrive}
                      className="text-steel-muted hover:underline"
                    >
                      Disconnect
                    </button>
                  )}
                </span>
              )}
            </div>
          ))}
          {!knowledge.enabled && (
            <div className="text-[11px] text-[color:var(--color-warning)]">
              Retrieval off — set RAG_PROVIDER=vector to enable.
            </div>
          )}
          <div className="flex gap-2">
            <button
              onClick={() => onReindex(false)}
              disabled={!knowledge.enabled}
              className="flex-1 text-xs font-medium text-steel-highlight bg-steel-highlight/10 hover:bg-steel-highlight/15 border border-steel-highlight/30 rounded-lg py-2 transition disabled:opacity-40"
            >
              Reindex
            </button>
            {devMode && (
              <button
                onClick={() => onReindex(true)}
                disabled={!knowledge.enabled}
                // Was `bg-white`, a literal #fff that dark mode cannot
                // override — `text-steel` on it measured 2.17:1 in dark. Task
                // 17's sweep converted it to the card surface token.
                className="flex-1 text-xs font-medium text-steel bg-navy-800 border border-navy-700/20 rounded-lg py-2 transition disabled:opacity-40"
              >
                Full rebuild
              </button>
            )}
          </div>
          {devMode && knowledge.docs.length > 0 && (
            <ul className="max-h-28 overflow-y-auto custom-scrollbar space-y-0.5 pt-1">
              {knowledge.docs.map((d) => (
                <li
                  key={d.path}
                  className="text-[11px] text-steel-dark flex justify-between gap-2"
                >
                  <span className="truncate">{d.path}</span>
                  <span className="text-steel-muted shrink-0">{d.chunk_count}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
