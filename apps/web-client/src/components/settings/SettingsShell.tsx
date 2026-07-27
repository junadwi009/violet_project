import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";
import type { SettingsValues } from "../../lib/api";

export type PanelProps = {
  values: SettingsValues;
  overridden: string[];
  patch: (changes: SettingsValues) => void;
  devMode: boolean;
};

export function SettingsShell({
  open,
  onClose,
  title,
  nav,
  children,
  error,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  nav: ReactNode;
  children: ReactNode;
  error: string | null;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const returnFocusTo = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    returnFocusTo.current = document.activeElement as HTMLElement | null;
    const node = panelRef.current;
    node?.querySelector<HTMLElement>("[role='tab'][aria-selected='true']")?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !node) return;
      const focusable = node.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      returnFocusTo.current?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-steel-dark/30 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        className="bg-navy-800 border border-navy-700/20 rounded-[1.5rem] w-full max-w-4xl h-[min(85vh,42rem)] shadow-2xl relative flex flex-col overflow-hidden"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-center gap-3 px-6 py-4 border-b border-navy-700/20 shrink-0">
          <h2 id="settings-title" className="text-lg font-semibold text-steel-dark">
            {title}
          </h2>
          <button
            onClick={onClose}
            aria-label="Close settings"
            className="ml-auto text-steel hover:text-steel-dark"
          >
            <X size={18} />
          </button>
        </header>

        {error && (
          <p
            role="alert"
            className="px-6 py-2 text-xs text-[color:var(--color-warning)] bg-[color:var(--color-warning)]/10 border-b border-navy-700/20 shrink-0"
          >
            {error}
          </p>
        )}

        <div className="flex flex-1 min-h-0">
          {nav}
          <div className="flex-1 overflow-y-auto custom-scrollbar p-6">{children}</div>
        </div>
      </div>
    </div>
  );
}
