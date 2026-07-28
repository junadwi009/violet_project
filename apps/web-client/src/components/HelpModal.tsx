import { X } from "lucide-react";

type HelpModalProps = {
  open: boolean;
  onClose: () => void;
  assistantName: string;
};

export function HelpModal({ open, onClose, assistantName }: HelpModalProps) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 bg-[color:var(--color-scrim)]/30 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-navy-800 border border-navy-700/20 p-8 rounded-[2rem] w-full max-w-md shadow-2xl relative"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-6 right-6 text-steel hover:text-steel-dark"
          title="Close"
        >
          <X size={18} />
        </button>
        <h3 className="text-xl font-semibold text-steel-dark mb-4">
          About {assistantName}
        </h3>
        <p className="text-sm text-steel leading-relaxed mb-4">
          {assistantName} is a local-first personal assistant. The language model runs
          through your configured provider (mock by default, or a local / OpenAI-compatible
          endpoint) — nothing is sent to a third party unless you point it there.
        </p>
        <p className="text-sm text-steel leading-relaxed mb-4">
          Memory is approval-gated: {assistantName} proposes candidates, and nothing is
          stored until you approve it in the Memory panel.
        </p>
        <button
          onClick={onClose}
          className="w-full bg-steel-ice hover:bg-steel/10 text-steel-dark font-medium py-2 px-4 rounded-xl text-sm transition mt-2"
        >
          Close
        </button>
      </div>
    </div>
  );
}
