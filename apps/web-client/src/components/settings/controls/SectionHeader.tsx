import { RotateCcw } from "lucide-react";

export function SectionHeader({
  title,
  description,
  modified,
  onReset,
}: {
  title: string;
  description?: string;
  modified: boolean;
  onReset?: () => void;
}) {
  return (
    <div className="flex items-start gap-2 pb-4 mb-5 border-b border-navy-700/20">
      <div className="min-w-0">
        <h3 className="text-base font-semibold text-steel-dark flex items-center gap-2">
          {title}
          {/* `role="img"`: ARIA does not allow naming a bare span (implicit
              role `generic`), so `aria-label` on its own would be dropped and
              the dot would carry no accessible name at all. */}
          {modified && (
            <span
              role="img"
              title="Changed from defaults"
              aria-label="Changed from defaults"
              className="w-1.5 h-1.5 rounded-full bg-steel-highlight"
            />
          )}
        </h3>
        {description && (
          <p className="text-[11px] text-steel/70 mt-1">{description}</p>
        )}
      </div>
      {onReset && (
        <button
          type="button"
          onClick={onReset}
          disabled={!modified}
          className="ml-auto shrink-0 flex items-center gap-1 text-[11px] text-steel hover:text-steel-highlight disabled:opacity-30 disabled:hover:text-steel"
        >
          <RotateCcw size={12} />
          Reset section
        </button>
      )}
    </div>
  );
}
