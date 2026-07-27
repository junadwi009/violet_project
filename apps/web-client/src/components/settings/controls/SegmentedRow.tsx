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
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium text-steel-dark">{label}</span>
      <div
        role="radiogroup"
        aria-label={label}
        className="ml-auto inline-flex rounded-full bg-steel-ice border border-navy-700/20 p-0.5"
      >
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={option.value === value}
            onClick={() => onSelect(option.value)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition ${
              option.value === value
                ? "bg-steel-highlight/15 text-steel-highlight"
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
