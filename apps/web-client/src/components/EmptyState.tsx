import { FormEvent, ReactNode } from "react";

type EmptyStateProps = {
  assistantName: string;
  composer: ReactNode;
  onQuickPrompt: (text: string) => void;
};

const QUICK_PROMPTS = [
  "Bar chart of sales: Jan 120, Feb 150, Mar 90, Apr 200",
  "Interactive dashboard analyzing 3 products by revenue and growth",
  "Draft a short status update",
];

export function EmptyState({ assistantName, composer, onQuickPrompt }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center text-center w-full space-y-8 max-w-2xl mx-auto px-6 h-full">
      <div className="relative flex flex-col items-center">
        <div className="absolute inset-0 rounded-full glowing-avatar opacity-60 blur-3xl w-36 h-36" />
        <div className="relative w-36 h-36 overflow-hidden z-10 soft-edge-avatar rounded-full">
          <div className="w-full h-full rounded-full bg-[radial-gradient(circle_at_50%_35%,#c77dff_0%,#9d4edd_45%,#7b2cbf_75%,#5a189a_100%)]" />
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="font-mono text-5xl font-semibold text-white/90 drop-shadow">
              V
            </span>
          </div>
        </div>
      </div>

      <div className="space-y-1">
        <h1 className="text-4xl font-light text-steel-dark tracking-wide">
          Ready when you are
        </h1>
        <p className="text-xs text-steel/60">
          Start a conversation with {assistantName}
        </p>
      </div>

      <div className="w-full max-w-xl px-4">{composer}</div>

      <div className="flex flex-wrap items-center justify-center gap-2">
        {QUICK_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onQuickPrompt(prompt)}
            className="px-3.5 py-2 rounded-full bg-white/70 border border-navy-700/20 text-xs text-steel hover:text-steel-dark hover:bg-white transition shadow-sm"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
