import { useEffect, useId, useState } from "react";

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

  const inputId = useId();
  const hintId = useId();

  // The surface token is `bg-navy-800`, not `bg-white`: `bg-white` is a literal
  // #fff that `[data-theme="dark"]` cannot override, while `text-steel-dark`
  // inverts to near-white (#f2ecfa) — 1.16:1, i.e. the user's own typing
  // invisible. `navy-800` is #ffffff in light and #241d31 in dark, giving
  // 17.91:1 and 14.02:1.
  return (
    <div>
      <label
        htmlFor={inputId}
        className="block text-xs font-medium text-steel-dark mb-1"
      >
        {label}
      </label>
      <input
        id={inputId}
        value={local}
        placeholder={placeholder}
        aria-describedby={hint ? hintId : undefined}
        onChange={(event) => {
          setLocal(event.target.value);
          onChange(event.target.value);
        }}
        className="w-full text-xs font-mono bg-navy-800 border border-navy-700/20 rounded-lg px-2.5 py-1.5 text-steel-dark focus:outline-none focus:ring-1 focus:ring-steel-highlight/30"
      />
      {hint && (
        <p id={hintId} className="text-[11px] text-steel/60 mt-1">
          {hint}
        </p>
      )}
    </div>
  );
}
