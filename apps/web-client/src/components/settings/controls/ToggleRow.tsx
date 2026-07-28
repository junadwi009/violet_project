import { useId } from "react";
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
  const hintId = useId();

  return (
    <div className="flex items-start gap-2 text-xs text-steel-dark">
      {icon}
      <div className="min-w-0">
        <span className="font-medium">{label}</span>
        {hint && (
          <p id={hintId} className="text-[11px] text-steel-muted mt-0.5">
            {hint}
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={onToggle}
        role="switch"
        aria-checked={on}
        aria-label={label}
        aria-describedby={hint ? hintId : undefined}
        // WCAG 1.4.11 wants 3:1 for the visual information that identifies a
        // control and its state. The off track was `bg-navy-700/30` — 1.11:1
        // against the card, i.e. an invisible pill; `bg-steel/70` is 3.65:1
        // light / 4.26:1 dark. The knob is `bg-navy-950`, not a literal white:
        // navy-950 is #f7f4fa in light (indistinguishable from the white knob
        // it replaces) and #14101c in dark, so it stays legible against the
        // *on* track too — white on the dark accent was 2.64:1 for violet and
        // 1.42:1 for amber. Knob-vs-track now: off 3.32/5.08, on 6.52/7.12.
        className={`ml-auto shrink-0 w-9 h-5 rounded-full transition relative ${
          on ? "bg-steel-highlight" : "bg-steel/70"
        }`}
      >
        <span
          className={`absolute top-0.5 w-4 h-4 rounded-full bg-navy-950 shadow transition-all ${
            on ? "left-4" : "left-0.5"
          }`}
        />
      </button>
    </div>
  );
}
