import { useId, useState } from "react";
import { AlertTriangle, Download, Lock } from "lucide-react";
import { downloadExport, type ExportError } from "../../../lib/api";
import { SectionHeader } from "../controls/SectionHeader";

const LOCKED_LABELS: Record<string, string> = {
  llm_provider: "LLM provider",
  agent_tools_enabled: "Agent tools",
  allow_shell_tools: "Shell tools",
  allow_email_tools: "Email tools",
  allow_file_delete: "File deletion",
  require_confirmation_for_risky_tools: "Confirm risky tools",
  tool_confirm_threshold: "Confirmation threshold",
  max_tool_iterations: "Max tool iterations",
};

const CONFIRM_WORD = "delete";

function renderValue(value: string | number | boolean) {
  if (typeof value !== "boolean") return String(value);
  return value ? "on" : "off";
}

/** Guidance per failure kind.
 *
 * These three have genuinely different fixes and must not collapse into one
 * "export failed" line:
 *   - client_token_missing: the *browser build* has no token. Nothing was even
 *     sent. Fixed in the client's env + a dev-server restart.
 *   - server_not_configured: the *server* has no token, so export is disabled
 *     outright. No client-side change can help.
 *   - unauthorized: both sides have a token and they disagree.
 */
function describeExportError(error: ExportError): {
  title: string;
  detail: string;
} {
  switch (error.kind) {
    case "client_token_missing":
      return {
        title: "Export is unavailable in this build",
        detail:
          "VITE_VIOLET_API_TOKEN is not set for the web client, so the request cannot be authorized and is not attempted. Set it in apps/web-client/.env.local to the same value as the server's VIOLET_API_TOKEN, then restart the dev server.",
      };
    case "server_not_configured":
      return {
        title: "Export is disabled on the server",
        detail:
          "The assistant is running without VIOLET_API_TOKEN, which disables /api/export entirely. Set VIOLET_API_TOKEN in the server environment and restart it. No change in the browser will help.",
      };
    case "unauthorized":
      return {
        title: "Export was rejected",
        detail:
          "The server has a token configured, but the one this client sent does not match it. Make VITE_VIOLET_API_TOKEN identical to the server's VIOLET_API_TOKEN, then restart the dev server so the new value is compiled in.",
      };
    case "http_error":
      return {
        title: `Export failed (HTTP ${error.status})`,
        detail: error.detail,
      };
    case "network_error":
      return {
        title: "Could not reach the assistant",
        detail: `${error.message} — check that the API is running and that this origin is allowed by its CORS policy.`,
      };
  }
}

/** Data & privacy.
 *
 * The only panel that does not take `PanelProps`: it edits no preferences, so
 * `values` / `overridden` / `patchNow` / `patchDebounced` would all be dead
 * props. It gets exactly the two things it uses.
 *
 * The destructive confirmation is INLINE rather than a nested dialog on
 * purpose. `SettingsShell` listens for Escape in the *capture* phase, so it
 * would pre-empt a nested dialog's own Escape handler and close the whole
 * Settings dialog out from under it. Keeping the confirmation in the panel
 * body means there is nothing to nest and Escape keeps its single meaning.
 */
export function DataPanel({
  locked,
  onDeleteAllSessions,
}: {
  locked: Record<string, string | number | boolean>;
  onDeleteAllSessions: () => Promise<void>;
}) {
  const confirmInputId = useId();
  const [confirmText, setConfirmText] = useState("");
  const [clearing, setClearing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<ExportError | null>(null);
  const [exportedFile, setExportedFile] = useState<string | null>(null);

  // Knowable before any request: with no client token the fetch could not
  // possibly be authorized, so `downloadExport` short-circuits. Rendering an
  // enabled button that we already know does nothing is the thing to avoid,
  // so this is resolved at render time rather than on click.
  const clientTokenMissing = !import.meta.env.VITE_VIOLET_API_TOKEN;

  // Both of these mean "no request from this browser can succeed as things
  // stand" — one because the client cannot authorize, one because the server
  // refuses to serve at all. In either case we show the fix instead of a
  // download control.
  const exportUnavailable =
    clientTokenMissing || exportError?.kind === "server_not_configured";

  const unavailableReason: ExportError | null = clientTokenMissing
    ? { kind: "client_token_missing" }
    : exportError?.kind === "server_not_configured"
      ? exportError
      : null;

  // Shown next to the download button — a failure that is worth retrying
  // as-is, or after a config change, rather than one that disables export.
  const retryableError =
    exportError && exportError.kind !== "server_not_configured"
      ? exportError
      : null;

  async function handleExport() {
    setExporting(true);
    setExportError(null);
    setExportedFile(null);
    try {
      // NOTE: downloadExport does NOT throw. It returns a discriminated union
      // so the caller can distinguish failures that have different fixes.
      const outcome = await downloadExport();
      if (outcome.ok) {
        setExportedFile(outcome.filename);
      } else {
        setExportError(outcome.error);
      }
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Data & privacy"
        description="Everything here is stored locally on this machine."
        modified={false}
      />

      <div>
        <h4 className="text-xs font-semibold text-steel uppercase tracking-wider mb-2">
          Backup
        </h4>

        {exportUnavailable && unavailableReason ? (
          <div
            role="status"
            className="p-3 rounded-xl border border-[color:var(--color-warning)]/40 bg-[color:var(--color-warning)]/10 space-y-1"
          >
            <p className="flex items-center gap-1.5 text-xs font-semibold text-steel-dark">
              <AlertTriangle
                size={13}
                className="text-[color:var(--color-warning)] shrink-0"
              />
              {describeExportError(unavailableReason).title}
            </p>
            <p className="text-[11px] text-steel-dark leading-relaxed">
              {describeExportError(unavailableReason).detail}
            </p>
          </div>
        ) : (
          <>
            <button
              type="button"
              onClick={handleExport}
              disabled={exporting}
              className="flex items-center justify-center gap-2 w-full text-xs font-medium text-steel-highlight bg-steel-highlight/10 hover:bg-steel-highlight/15 border border-steel-highlight/30 rounded-lg py-2.5 transition disabled:opacity-40"
            >
              <Download size={13} />
              {exporting ? "Preparing export…" : "Export all data as JSON"}
            </button>
            <p className="text-[11px] text-steel mt-1.5">
              Sessions, messages, memories, and your preference overrides. Do
              this before clearing anything.
            </p>
            {exportedFile && (
              <p
                role="status"
                className="text-[11px] text-[color:var(--color-success)] mt-1.5"
              >
                Downloaded{" "}
                <span className="font-mono">{exportedFile}</span>
              </p>
            )}
            {retryableError && (
              <div
                role="alert"
                className="mt-2 p-2.5 rounded-lg border border-[color:var(--color-danger)]/40 bg-[color:var(--color-danger)]/10 space-y-1"
              >
                <p className="text-[11px] font-semibold text-[color:var(--color-danger)]">
                  {describeExportError(retryableError).title}
                </p>
                <p className="text-[11px] text-steel-dark leading-relaxed">
                  {describeExportError(retryableError).detail}
                </p>
              </div>
            )}
          </>
        )}
      </div>

      <div>
        <h4 className="flex items-center gap-1.5 text-xs font-semibold text-steel uppercase tracking-wider mb-2">
          <Lock size={12} />
          Safety configuration
        </h4>
        {/* Status, never a control. These flags decide whether shell/email/
            file-delete tools can run at all; putting any affordance here that
            could change them would defeat the point of their being read-only.
            Rendered as plain text with no input, button, or link. */}
        <div className="p-3 bg-steel-ice rounded-xl border border-navy-700/20 space-y-1.5">
          {Object.entries(locked).map(([key, value]) => (
            <div key={key} className="flex items-center gap-2 text-[11px]">
              <span className="text-steel-dark">
                {LOCKED_LABELS[key] ?? key}
              </span>
              <span className="ml-auto font-mono text-steel">
                {renderValue(value)}
              </span>
            </div>
          ))}
          <p className="text-[11px] text-steel pt-1.5 border-t border-navy-700/10">
            Read-only. These are set in <span className="font-mono">.env</span>{" "}
            and deliberately cannot be changed from the browser.
          </p>
        </div>
      </div>

      <div>
        <h4 className="text-xs font-semibold text-[color:var(--color-danger)] uppercase tracking-wider mb-2">
          Danger zone
        </h4>
        <div className="p-3 rounded-xl border border-[color:var(--color-danger)]/40 bg-[color:var(--color-danger)]/5 space-y-2">
          <p className="text-[11px] text-steel-dark">
            Deletes every session and message, and any memory candidates still
            waiting on them. Approved memories are kept. This cannot be undone.
          </p>
          {exportUnavailable ? (
            // The backup path is the stated justification for this control
            // being safe to offer. If export cannot run, say so here rather
            // than let the section imply a backup exists.
            <p className="flex items-start gap-1.5 text-[11px] font-medium text-[color:var(--color-danger)]">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              Export is unavailable, so there is no backup to fall back on. See
              Backup above.
            </p>
          ) : (
            <p className="text-[11px] text-steel">
              Export first if you want a copy.
            </p>
          )}
          {/* A visible label, not just a placeholder: this is the only
              on-screen instruction for an irreversible delete, and a
              placeholder disappears the moment the user starts typing —
              exactly when they are checking what they typed. The
              placeholder is kept as a secondary, in-field echo of the same
              word, so it needs to hold contrast too, not just decorate. */}
          <label
            htmlFor={confirmInputId}
            className="block text-[11px] font-medium text-steel-dark"
          >
            Type <span className="font-mono">{CONFIRM_WORD}</span> to confirm
          </label>
          <input
            id={confirmInputId}
            value={confirmText}
            onChange={(event) => setConfirmText(event.target.value)}
            placeholder={CONFIRM_WORD}
            autoComplete="off"
            spellCheck={false}
            className="w-full text-xs bg-navy-900 border border-navy-700/40 rounded-lg px-2.5 py-1.5 text-steel-dark placeholder:text-steel"
          />
          <button
            type="button"
            disabled={confirmText !== CONFIRM_WORD || clearing}
            onClick={async () => {
              setClearing(true);
              try {
                await onDeleteAllSessions();
                setConfirmText("");
              } finally {
                setClearing(false);
              }
            }}
            // Outlined, not a solid red fill: `text-navy-950` on either danger
            // value fails contrast badly in dark mode (~1.5:1). Bold danger-
            // colored text inside a full-strength danger border is just as
            // loud and stays legible in both themes.
            //
            // The resting fill is transparent on purpose. Measured in the
            // browser: a 15% danger tint *on top of* this section's own 5%
            // tint lightens dark-mode background enough to drop the label to
            // 4.29:1, under AA. Transparent leaves it at 5.47:1 dark / 5.95:1
            // light, and the tint moves to hover only.
            className="w-full text-xs font-semibold text-[color:var(--color-danger)] bg-transparent hover:bg-[color:var(--color-danger)]/15 border border-[color:var(--color-danger)] rounded-lg py-2 transition disabled:opacity-40 disabled:hover:bg-transparent"
          >
            {clearing ? "Clearing…" : "Clear all sessions"}
          </button>
        </div>
      </div>
    </div>
  );
}
