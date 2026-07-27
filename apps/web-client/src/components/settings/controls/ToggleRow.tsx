import type { ReactNode } from "react";

export function ToggleRow({
  label,
  hint,
  on,
  onToggle,
  icon,
}: {
  label: string;
  hint?: string;
  on: boolean;
  onToggle: () => void;
  icon?: ReactNode;
}) {
  return (
    <div className="flex items-start gap-2 text-xs text-steel-dark">
      {icon}
      <div className="min-w-0">
        <span className="font-medium">{label}</span>
        {hint && <p className="text-[11px] text-steel/60 mt-0.5">{hint}</p>}
      </div>
      <button
        type="button"
        onClick={onToggle}
        role="switch"
        aria-checked={on}
        aria-label={label}
        className={`ml-auto shrink-0 w-9 h-5 rounded-full transition relative ${
          on ? "bg-steel-highlight" : "bg-navy-700/30"
        }`}
      >
        <span
          className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${
            on ? "left-4" : "left-0.5"
          }`}
        />
      </button>
    </div>
  );
}
