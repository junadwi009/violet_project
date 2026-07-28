import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Check } from "lucide-react";
import type { KnowledgeInfo, ReindexReport } from "../../../lib/api";
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
  onReindex: (full: boolean, source?: string) => Promise<ReindexReport>;
  onConnectGDrive: () => Promise<void>;
  onDisconnectGDrive: () => Promise<void>;
  onReset: () => void;
}) {
  const modified = KNOWLEDGE_KEYS.some((key) => overridden.includes(key));

  // Every action in this panel used to report *only* through App's status
  // pill, which sits in `WorkspaceHeader` — underneath the settings scrim.
  // A failed reindex, full rebuild, or Drive connect/disconnect was therefore
  // completely silent to a user who is, by definition, looking at this dialog.
  // Both outcomes are owned here now; the pill still fires for the closed case.
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // These land at the bottom of a scrolling panel; `block: "nearest"` brings
  // them into view only when they are actually below the fold. A result the
  // user has to go looking for is barely better than one behind the scrim.
  const resultRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (actionError || notice)
      resultRef.current?.scrollIntoView({ block: "nearest" });
  }, [actionError, notice]);

  /** One wrapper for all four actions so none of them can quietly grow a
   *  swallowed failure again. `verb` is used to label the failure, so it reads
   *  as a sentence rather than as a bare exception string. */
  async function run(verb: string, action: () => Promise<string>) {
    setBusy(verb);
    setActionError(null);
    setNotice(null);
    try {
      setNotice(await action());
    } catch (error) {
      setActionError(
        `${verb} failed: ${error instanceof Error ? error.message : "unknown error"}`,
      );
    } finally {
      setBusy(null);
    }
  }

  function summarize(report: ReindexReport) {
    const base = `Indexed ${report.indexed}, skipped ${report.skipped}, removed ${report.removed} (${report.chunks} chunks).`;
    // Per-document errors come back *inside* a 200 response, so a run that
    // "succeeded" can still have dropped files. Saying so is the whole point.
    return report.errors.length > 0
      ? `${base} ${report.errors.length} document(s) could not be read: ${report.errors
          .map((e) => e.path)
          .join(", ")}`
      : base;
  }

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
                  onClick={() =>
                    run("Connect", async () => {
                      await onConnectGDrive();
                      return "Google Drive connected.";
                    })
                  }
                  disabled={busy !== null}
                  className="ml-auto text-steel-highlight hover:underline disabled:opacity-40 disabled:no-underline"
                >
                  Connect
                </button>
              )}
              {s.name === "gdrive" && s.connected && (
                <span className="ml-auto flex items-center gap-2">
                  <button
                    onClick={() =>
                      run("Sync", async () =>
                        summarize(await onReindex(false, "gdrive")),
                      )
                    }
                    disabled={busy !== null}
                    className="text-steel-highlight hover:underline disabled:opacity-40 disabled:no-underline"
                  >
                    Sync
                  </button>
                  {devMode && (
                    <button
                      onClick={() =>
                        run("Disconnect", async () => {
                          await onDisconnectGDrive();
                          return "Google Drive disconnected.";
                        })
                      }
                      disabled={busy !== null}
                      className="text-steel-muted hover:underline disabled:opacity-40 disabled:no-underline"
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
              onClick={() =>
                run("Reindex", async () => summarize(await onReindex(false)))
              }
              disabled={!knowledge.enabled || busy !== null}
              className="flex-1 text-xs font-medium text-steel-highlight bg-steel-highlight/10 hover:bg-steel-highlight/15 border border-steel-highlight/30 rounded-lg py-2 transition disabled:opacity-40"
            >
              {busy === "Reindex" ? "Reindexing…" : "Reindex"}
            </button>
            {devMode && (
              <button
                onClick={() =>
                  run("Full rebuild", async () =>
                    summarize(await onReindex(true)),
                  )
                }
                disabled={!knowledge.enabled || busy !== null}
                // Was `bg-white`, a literal #fff that dark mode cannot
                // override — `text-steel` on it measured 2.17:1 in dark. Task
                // 17's sweep converted it to the card surface token.
                className="flex-1 text-xs font-medium text-steel bg-navy-800 border border-navy-700/20 rounded-lg py-2 transition disabled:opacity-40"
              >
                {busy === "Full rebuild" ? "Rebuilding…" : "Full rebuild"}
              </button>
            )}
          </div>
          {/* Rendered on this card's own `bg-steel-ice`, with no extra tint —
              the same reasoning as DataPanel's danger zone. Measured
              in-browser on the composited surface: `--color-danger` 6.35 dark,
              which is exactly index.css's recorded "danger plain on
              steel-ice" figure; `text-steel-dark` is the body colour this
              card already uses throughout. */}
          <div ref={resultRef} className="empty:hidden">
            {actionError && (
              <p
                role="alert"
                className="flex items-start gap-1.5 text-[11px] leading-relaxed text-[color:var(--color-danger)]"
              >
                <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                <span>{actionError}</span>
              </p>
            )}
            {notice && (
              <p
                role="status"
                className="flex items-start gap-1.5 text-[11px] leading-relaxed text-steel-dark"
              >
                <Check
                  size={12}
                  className="mt-0.5 shrink-0 text-[color:var(--color-success)]"
                />
                <span>{notice}</span>
              </p>
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
