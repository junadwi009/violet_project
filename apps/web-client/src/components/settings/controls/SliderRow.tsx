import { useEffect, useState } from "react";

export function SliderRow({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format?: (value: number) => string;
  onChange: (value: number) => void;
}) {
  // Local state keeps the thumb responsive; the parent debounces the write.
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);

  return (
    <div>
      <div className="flex items-center justify-between text-xs text-steel-dark mb-1">
        <span className="font-medium">{label}</span>
        <span className="font-mono text-steel">
          {format ? format(local) : local.toFixed(1)}
        </span>
      </div>
      <input
        type="range"
        aria-label={label}
        min={min}
        max={max}
        step={step}
        value={local}
        onChange={(event) => {
          const next = Number(event.target.value);
          setLocal(next);
          onChange(next);
        }}
        className="w-full accent-steel-highlight"
      />
    </div>
  );
}
