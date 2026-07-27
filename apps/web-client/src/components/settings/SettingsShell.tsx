import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";
import type { SettingsValues } from "../../lib/api";
import { settingsPanelDomId, settingsTabDomId } from "./ids";

export type PanelProps = {
  values: SettingsValues;
  overridden: string[];
  patch: (changes: SettingsValues) => void;
  devMode: boolean;
};

// Nav tabs carry `tabindex="-1"` under roving tabindex, so they are NOT in the
// browser's tab order; including them would make the trap's computed first/last
// disagree with where Tab actually goes.
const FOCUSABLE_SELECTOR = [
  'a[href]:not([tabindex="-1"])',
  'button:not([disabled]):not([tabindex="-1"])',
  'input:not([disabled]):not([tabindex="-1"])',
  'select:not([disabled]):not([tabindex="-1"])',
  'textarea:not([disabled]):not([tabindex="-1"])',
  '[tabindex]:not([tabindex="-1"])',
].join(", ");

export function SettingsShell({
  open,
  onClose,
  title,
  nav,
  activeTab,
  children,
  error,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  nav: ReactNode;
  /** id of the currently selected `NavItem`, so the panel region can be wired
   *  back to its tab (`aria-labelledby` / `aria-controls`). */
  activeTab: string;
  children: ReactNode;
  error: string | null;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const returnFocusTo = useRef<HTMLElement | null>(null);
  const backdropPointerDown = useRef(false);
  const titleId = useId();

  // Held in a ref so the focus effect below can depend on `[open]` alone.
  // Callers pass an inline arrow (`onClose={() => setSettingsOpen(false)}`), so
  // depending on `onClose` would re-run the effect — and fire its
  // focus-returning cleanup — on every single parent render, yanking focus out
  // of whatever the user was typing in.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return;
    returnFocusTo.current = document.activeElement as HTMLElement | null;
    const node = panelRef.current;
    const initial =
      node?.querySelector<HTMLElement>("[role='tab'][aria-selected='true']") ??
      node?.querySelector<HTMLElement>("[role='tab']") ??
      node?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
    initial?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !node) return;
      const focusable = node.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
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
    // This cleanup now runs only when `open` flips to false, or on unmount —
    // i.e. only on an actual close.
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      const target = returnFocusTo.current;
      returnFocusTo.current = null;
      target?.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-steel-dark/30 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      // A drag that starts inside the panel (slider thumb, text selection) and
      // ends outside it still dispatches `click` on the backdrop. Close only
      // when both ends of the gesture were on the backdrop itself.
      onMouseDown={(event) => {
        backdropPointerDown.current = event.target === event.currentTarget;
      }}
      onClick={(event) => {
        if (event.target !== event.currentTarget) return;
        if (!backdropPointerDown.current) return;
        backdropPointerDown.current = false;
        onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="bg-navy-800 border border-navy-700/20 rounded-[1.5rem] w-full max-w-4xl h-[min(85vh,42rem)] shadow-2xl relative flex flex-col overflow-hidden"
      >
        <header className="flex items-center gap-3 px-6 py-4 border-b border-navy-700/20 shrink-0">
          <h2 id={titleId} className="text-lg font-semibold text-steel-dark">
            {title}
          </h2>
          <button
            type="button"
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
          <div
            role="tabpanel"
            id={activeTab ? settingsPanelDomId(activeTab) : undefined}
            aria-labelledby={activeTab ? settingsTabDomId(activeTab) : undefined}
            className="flex-1 overflow-y-auto custom-scrollbar p-6"
          >
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
