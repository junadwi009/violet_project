import { useRef } from "react";

export function SegmentedRow<T extends string>({
  label,
  value,
  options,
  onSelect,
}: {
  label: string;
  value: T;
  options: readonly { value: T; label: string }[];
  onSelect: (value: T) => void;
}) {
  const optionRefs = useRef(new Map<T, HTMLButtonElement>());
  const checkedIndex = options.findIndex((option) => option.value === value);
  // With nothing checked (a value outside `options`) the group would have no
  // tab stop at all; fall back to the first option.
  const tabbableIndex = checkedIndex >= 0 ? checkedIndex : 0;

  function moveTo(index: number) {
    const option = options[index];
    if (!option) return;
    onSelect(option.value);
    optionRefs.current.get(option.value)?.focus();
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium text-steel-dark">{label}</span>
      <div
        role="radiogroup"
        aria-label={label}
        className="ml-auto inline-flex rounded-full bg-steel-ice border border-navy-700/20 p-0.5"
        // Roving tabindex: the group is one tab stop and arrows move both
        // selection and DOM focus, per the ARIA radiogroup pattern.
        onKeyDown={(event) => {
          if (options.length === 0) return;
          let next: number;
          switch (event.key) {
            case "ArrowRight":
            case "ArrowDown":
              next = (tabbableIndex + 1) % options.length;
              break;
            case "ArrowLeft":
            case "ArrowUp":
              next = (tabbableIndex - 1 + options.length) % options.length;
              break;
            case "Home":
              next = 0;
              break;
            case "End":
              next = options.length - 1;
              break;
            default:
              return;
          }
          event.preventDefault();
          moveTo(next);
        }}
      >
        {options.map((option, index) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={index === tabbableIndex}
            tabIndex={index === tabbableIndex ? 0 : -1}
            ref={(node) => {
              if (node) optionRefs.current.set(option.value, node);
              else optionRefs.current.delete(option.value);
            }}
            onClick={() => onSelect(option.value)}
            // The selected pill is an opaque raised chip on the `steel-ice`
            // track, not a tint of the accent over that track: tinting a
            // background with the very colour drawn on top of it strictly
            // reduces contrast, and `text-steel-highlight` on
            // `bg-steel-highlight/15` missed AA in 5 of 10 theme x accent
            // combinations (worst 3.65:1). `bg-navy-800` reduces the pairing to
            // accent-on-card, which the theme-token work certified across all
            // ten (worst here 5.02:1).
            className={`px-3 py-1 rounded-full text-xs font-medium transition ${
              index === tabbableIndex
                ? "bg-navy-800 text-steel-highlight shadow-sm"
                : "text-steel hover:text-steel-dark"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
