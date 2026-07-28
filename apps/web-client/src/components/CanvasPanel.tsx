import { X } from "lucide-react";
import { Artifact } from "../lib/api";
import { ChartArtifact, HtmlArtifact, FileArtifact } from "./ArtifactView";

type Props = {
  artifacts: Artifact[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onClose: () => void;
};

export function CanvasPanel({ artifacts, activeId, onSelect, onClose }: Props) {
  const active = artifacts.find((a) => a.id === activeId) ?? artifacts[0];
  if (!active) return null;
  const body =
    active.kind === "chartjs" ? (
      <ChartArtifact artifact={active} />
    ) : active.kind === "docx" || active.kind === "pptx" ? (
      <FileArtifact artifact={active} />
    ) : (
      <HtmlArtifact artifact={active} />
    );
  return (
    <aside className="fixed inset-0 z-40 lg:static lg:inset-auto h-full w-full lg:w-[46%] shrink-0 border-l border-navy-700/20 bg-navy-800 flex flex-col">
      <header className="flex items-center gap-2 px-4 py-3 border-b border-navy-700/15">
        <span className="text-sm font-semibold text-steel-dark truncate">
          {active.title || "Canvas"}
        </span>
        <span className="text-[10px] uppercase tracking-wider text-steel-muted">
          {active.kind}
        </span>
        <button
          onClick={onClose}
          className="ml-auto w-7 h-7 rounded-lg flex items-center justify-center text-steel hover:bg-steel-ice"
          title="Close canvas"
        >
          <X size={15} />
        </button>
      </header>
      {artifacts.length > 1 && (
        <div className="flex gap-1.5 px-3 py-2 overflow-x-auto border-b border-navy-700/10">
          {artifacts.map((a) => (
            <button
              key={a.id}
              onClick={() => onSelect(a.id)}
              className={`px-2.5 py-1 rounded-lg text-[11px] whitespace-nowrap border transition ${
                a.id === active.id
                  ? "bg-steel-highlight/10 text-steel-highlight border-steel-highlight/30"
                  : "bg-steel-ice text-steel border-navy-700/15"
              }`}
            >
              {a.title || a.kind}
            </button>
          ))}
        </div>
      )}
      <div className="flex-1 overflow-y-auto custom-scrollbar">{body}</div>
    </aside>
  );
}
