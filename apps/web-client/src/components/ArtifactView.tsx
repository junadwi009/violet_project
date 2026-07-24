import { useEffect, useRef, useState } from "react";
import { Chart } from "chart.js/auto";
import { BarChart3, LayoutDashboard, Maximize2, Minimize2 } from "lucide-react";
import { Artifact } from "../lib/api";

// Locked-down sandbox for HTML artifacts: scripts may run, but no same-origin access and a CSP
// that blocks all network — so LLM-generated dashboards can't reach the app or exfiltrate data.
const HTML_CSP =
  "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; " +
  "script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; " +
  "connect-src 'none'; base-uri 'none'; form-action 'none'\">";

function ChartArtifact({ artifact }: { artifact: Artifact }) {
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

function HtmlArtifact({ artifact }: { artifact: Artifact }) {
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

export function ArtifactView({ artifact }: { artifact: Artifact }) {
  const isChart = artifact.kind === "chartjs";
  return (
    <div className="mt-3 rounded-xl border border-navy-700/25 bg-white overflow-hidden shadow-sm">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-navy-700/15 bg-navy-900/60">
        {isChart ? (
          <BarChart3 size={14} className="text-steel-highlight" />
        ) : (
          <LayoutDashboard size={14} className="text-steel-highlight" />
        )}
        <span className="text-xs font-semibold text-steel-dark">
          {artifact.title || (isChart ? "Chart" : "Dashboard")}
        </span>
        <span className="ml-auto text-[10px] text-steel/50 uppercase tracking-wider">
          {artifact.kind}
        </span>
      </div>
      {isChart ? <ChartArtifact artifact={artifact} /> : <HtmlArtifact artifact={artifact} />}
    </div>
  );
}
