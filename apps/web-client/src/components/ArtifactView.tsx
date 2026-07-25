import { useEffect, useRef, useState } from "react";
import { Chart } from "chart.js/auto";
import {
  BarChart3,
  LayoutDashboard,
  Maximize2,
  Minimize2,
  FileText,
  Presentation,
  Download,
} from "lucide-react";
import { Artifact } from "../lib/api";

// Locked-down sandbox for HTML artifacts: scripts may run, but no same-origin access and a CSP
// that blocks all network — so LLM-generated dashboards can't reach the app or exfiltrate data.
const HTML_CSP =
  "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; " +
  "script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; " +
  "connect-src 'none'; base-uri 'none'; form-action 'none'\">";

export function ChartArtifact({ artifact }: { artifact: Artifact }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canvasRef.current || !artifact.spec) return;
    let chart: Chart | null = null;
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      chart = new Chart(canvasRef.current, artifact.spec as any);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not render chart");
    }
    return () => chart?.destroy();
  }, [artifact.spec]);

  if (error) {
    return <div className="text-xs text-red-600 p-3">Chart error: {error}</div>;
  }
  return (
    <div className="p-3">
      <div className="relative w-full" style={{ height: 320 }}>
        <canvas ref={canvasRef} />
      </div>
    </div>
  );
}

export function HtmlArtifact({ artifact }: { artifact: Artifact }) {
  const [expanded, setExpanded] = useState(false);
  const srcDoc = `<!doctype html><html><head><meta charset="utf-8">${HTML_CSP}</head><body>${artifact.html ?? ""}</body></html>`;
  return (
    <div className="relative">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="absolute top-2 right-2 z-10 w-7 h-7 rounded-lg bg-white/80 border border-navy-700/20 flex items-center justify-center text-steel hover:text-steel-dark transition"
        title={expanded ? "Shrink" : "Expand"}
      >
        {expanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
      </button>
      <iframe
        title={artifact.title || "Dashboard"}
        sandbox="allow-scripts"
        srcDoc={srcDoc}
        className="w-full rounded-b-xl bg-white"
        style={{ height: expanded ? 700 : 380, border: "none" }}
      />
    </div>
  );
}

function base64ToBlob(base64: string, mime: string): Blob {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}

export function FileArtifact({ artifact }: { artifact: Artifact }) {
  const isPptx = artifact.kind === "pptx";
  function download() {
    if (!artifact.file_base64) return;
    const blob = base64ToBlob(
      artifact.file_base64,
      artifact.mime || "application/octet-stream",
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = artifact.filename || (isPptx ? "presentation.pptx" : "document.docx");
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className="flex items-center gap-3 p-4">
      <div className="w-11 h-11 rounded-xl bg-steel-highlight/10 flex items-center justify-center text-steel-highlight shrink-0">
        {isPptx ? <Presentation size={20} /> : <FileText size={20} />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-steel-dark truncate">
          {artifact.filename || (isPptx ? "presentation.pptx" : "document.docx")}
        </p>
        <p className="text-[11px] text-steel/60 uppercase tracking-wider">
          {isPptx ? "PowerPoint" : "Word document"} · ready to download
        </p>
      </div>
      <button
        onClick={download}
        className="inline-flex items-center gap-1.5 bg-steel-dark hover:bg-black text-white text-xs font-semibold px-3.5 py-2 rounded-lg transition shrink-0"
      >
        <Download size={14} />
        Download
      </button>
    </div>
  );
}

export function ArtifactView({
  artifact,
  compact = false,
  onOpen,
}: {
  artifact: Artifact;
  compact?: boolean;
  onOpen?: () => void;
}) {
  const isChart = artifact.kind === "chartjs";
  const isFile = artifact.kind === "docx" || artifact.kind === "pptx";
  const icon = isChart ? (
    <BarChart3 size={14} className="text-steel-highlight" />
  ) : isFile ? (
    artifact.kind === "pptx" ? (
      <Presentation size={14} className="text-steel-highlight" />
    ) : (
      <FileText size={14} className="text-steel-highlight" />
    )
  ) : (
    <LayoutDashboard size={14} className="text-steel-highlight" />
  );
  const title =
    artifact.title || (isChart ? "Chart" : isFile ? "Document" : "Dashboard");

  // Compact card: just a clickable header that opens the artifact in the canvas.
  if (compact) {
    return (
      <button
        type="button"
        onClick={onOpen}
        className="mt-3 w-full flex items-center gap-2 px-3 py-2.5 rounded-xl border border-navy-700/25 bg-white shadow-sm hover:border-steel-highlight/40 transition text-left"
      >
        {icon}
        <span className="text-xs font-semibold text-steel-dark truncate">{title}</span>
        <span className="ml-auto text-[10px] text-steel-highlight uppercase tracking-wider flex items-center gap-1">
          <Maximize2 size={11} /> Open in canvas
        </span>
      </button>
    );
  }

  return (
    <div className="mt-3 rounded-xl border border-navy-700/25 bg-white overflow-hidden shadow-sm">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-navy-700/15 bg-navy-900/60">
        {icon}
        <span className="text-xs font-semibold text-steel-dark">{title}</span>
        <span className="ml-auto text-[10px] text-steel/50 uppercase tracking-wider">
          {artifact.kind}
        </span>
        {onOpen && (
          <button
            onClick={onOpen}
            className="text-steel/60 hover:text-steel-highlight transition"
            title="Open in canvas"
          >
            <Maximize2 size={12} />
          </button>
        )}
      </div>
      {isFile ? (
        <FileArtifact artifact={artifact} />
      ) : isChart ? (
        <ChartArtifact artifact={artifact} />
      ) : (
        <HtmlArtifact artifact={artifact} />
      )}
    </div>
  );
}
