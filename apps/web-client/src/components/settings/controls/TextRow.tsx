import { useEffect, useState } from "react";

export function TextRow({
  label,
  value,
  placeholder,
  hint,
  onChange,
}: {
  label: string;
  value: string;
  placeholder?: string;
  hint?: string;
  onChange: (value: string) => void;
}) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);

  return (
    <div>
      <label className="block text-xs font-medium text-steel-dark mb-1">
        {label}
      </label>
      <input
        value={local}
        placeholder={placeholder}
        onChange={(event) => {
          setLocal(event.target.value);
          onChange(event.target.value);
        }}
        className="w-full text-xs font-mono bg-white border border-navy-700/20 rounded-lg px-2.5 py-1.5 text-steel-dark focus:outline-none focus:ring-1 focus:ring-steel-highlight/30"
      />
      {hint && <p className="text-[11px] text-steel/60 mt-1">{hint}</p>}
    </div>
  );
}
